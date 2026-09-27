package com.mcscai.generator

import android.content.Context
import android.os.SystemClock
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

/**
 * 生成任务的串行执行器。
 *
 * 手机只有一个推理后端，并发跑多个任务只会互相拖慢，因此这里固定单线程依次执行：
 * 与服务器端「串行任务调度」的取舍一致。任务提交后立刻返回编号，网页按编号轮询进度，
 * 因此界面不会因为一次生成要跑几十秒而卡住。
 */
class JobRunner(private val context: Context) {

    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "mcscai-job")
    }

    /** 当前在跑的任务编号与它的取消标志。 */
    private val currentId = AtomicReference<String?>(null)
    private val cancelled = AtomicReference<Boolean>(false)

    /** 已完成任务的自增序号，用于日志与调试。 */
    private val finished = AtomicInteger(0)

    /** 提交任务并立刻返回排队中的记录。 */
    fun submit(payload: String): String {
        val request = JSONObject(payload)
        val task = request.getJSONObject("task")
        val candidateCount = request.optInt("candidate_count", 8)
        val modelId = request.optString("model_id", ModelCatalog.MODEL_ID)
        require(candidateCount in 1..64) { "候选数量必须在一至六十四之间" }

        // 提交前先校验需求，避免把明显非法的任务放进队列再失败。
        NativeEngine.validateTask(task.toString())?.let { throw IllegalArgumentException(it) }
        if (!ModelLoader.isReady(modelId)) throw IllegalStateException(ModelLoader.message)

        val job = JobStore.create(context, task.toString(), candidateCount, modelId)
        val jobId = job.getString("id")
        executor.submit { execute(jobId, task, candidateCount, modelId) }
        return job.toString()
    }

    /** 取消任务；正在跑的候选会在下一个检查点停下。 */
    fun cancel(jobId: String) {
        if (currentId.get() == jobId) cancelled.set(true)
        JobStore.update(context, jobId, status = "cancelled", message = "已取消")
    }

    /** 关闭线程池，等待在跑的任务结束。 */
    fun shutdown() {
        cancelled.set(true)
        executor.shutdownNow()
    }

    /** 一次生成任务的实际执行。 */
    private fun execute(jobId: String, task: JSONObject, candidateCount: Int, modelId: String) {
        currentId.set(jobId)
        cancelled.set(false)
        try {
            if (JSONObject(JobStore.read(context, jobId)).getString("status") == "cancelled") return
            val started = SystemClock.elapsedRealtime()
            JobStore.update(context, jobId, status = "running", progress = 1, message = "正在准备需求")
            // 候选按八视角生成；前八个是确定性的截面变换，超出部分再按温度采样。
            // 每个视角的需求特征在 Inference 内部按该视角重建，这里不预先算一份。
            val proposals = Inference.generate(task, candidateCount, modelId,
                shouldCancel = { cancelled.get() || Thread.currentThread().isInterrupted }) { done, total ->
                JobStore.update(context, jobId, progress = 5 + 60 * done / total,
                    message = "正在生成结构 $done/$total")
            }
            if (cancelled.get()) return
            val generated = SystemClock.elapsedRealtime()

            JobStore.update(context, jobId, progress = 70, message = "正在按本列前端摆放负载并模拟")
            val evaluations = JSONArray()
            val loadTasks = JSONArray()
            // JSONArray 不能直接 for-in，按索引取；同时 proposal 取出的是 JSONObject。
            for (index in 0 until proposals.length()) {
                if (cancelled.get()) return
                val proposal = proposals.getJSONObject(index)
                // 负载摆放：目标首块在该列最前方方块前两格；判定与服务器同一套协议。
                val loadTask = Inference.alignTargets(task, proposal)
                loadTasks.put(loadTask)
                evaluations.put(Inference.judge(loadTask, proposal))
            }

            // 优先选完整通过；否则优先展示半通过（负载能推动、只是时序或时限不合格）。
            val accepted = firstIndex(evaluations) { it.optBoolean("accepted") }
            val partial = firstIndex(evaluations) { it.optBoolean("partial") }
            val selected = accepted ?: partial ?: 0
            val evaluated = SystemClock.elapsedRealtime()
            val timing = JSONObject().put("generation_ms", generated - started)
                .put("evaluation_ms", evaluated - generated)
                .put("threads", ModelLoader.threads).put("decoder", "cached_decoder_v1")
            val result = JSONObject()
                .put("task", task)
                .put("proposals", proposals)
                .put("evaluations", evaluations)
                .put("load_tasks", loadTasks)
                .put("selected", selected)
                .put("accepted", accepted != null)
                .put("partial", partial != null)
                .put("model_id", modelId)
                .put("model_name", ModelCatalog.name(modelId))
                .put("architecture", "autoregressive_v1")
                .put("sampling_protocol", if (candidateCount > 8) "eight_view_greedy_then_sample_v1" else "eight_view_greedy_v1")
                .put("device", "本机")
                .put("candidate_budget", candidateCount)
                .put("timing", timing)

            JobStore.update(context, jobId, progress = 95, message = "正在保存运行回放",
                resultJson = result.toString())
            // 只给选中的候选保存回放：逐帧快照体积可观，全部保存会让手机存储迅速膨胀。
            Inference.saveReplay(context, jobId, selected, loadTasks.getJSONObject(selected),
                proposals.getJSONObject(selected))
            if (cancelled.get()) return
            val completed = SystemClock.elapsedRealtime()
            timing.put("replay_ms", completed - evaluated).put("total_ms", completed - started)
            Log.i("MCSCAI-Perf", "任务 $jobId：$timing")

            val message = when {
                accepted != null -> "已找到完整通过的结构"
                partial != null -> "未完整通过；已优先展示半通过候选（负载可推动，时序或时限不满足）"
                else -> "$candidateCount 个候选均未完整通过，可查看结构与失败原因"
            }
            JobStore.update(context, jobId, status = if (accepted != null) "success" else "not_found",
                progress = 100, message = message, resultJson = result.toString())
            finished.incrementAndGet()
        } catch (_: CancellationException) {
            JobStore.update(context, jobId, status = "cancelled", message = "已取消")
        } catch (error: Throwable) {
            JobStore.update(context, jobId, status = "error",
                message = "生成失败：" + (error.message ?: error.javaClass.simpleName).take(300))
        } finally {
            currentId.set(null)
        }
    }

    /** 找出第一个满足条件的下标；没有则返回 null。 */
    private inline fun firstIndex(rows: JSONArray, predicate: (JSONObject) -> Boolean): Int? {
        for (index in 0 until rows.length()) {
            if (predicate(rows.getJSONObject(index))) return index
        }
        return null
    }
}
