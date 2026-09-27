package com.mcscai.generator

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.pytorch.IValue
import org.pytorch.Tensor
import kotlin.math.max
import kotlin.math.min
import java.util.concurrent.CancellationException

/**
 * 模型推理与候选生成。
 *
 * 与 Python 侧的分工完全对应：需求特征构造、八视角截面变换、生成后的逆变换、负载摆放
 * 都在这里完成；真正的判定交给原生运算层（[NativeEngine.judge]）。
 *
 * 特征口径必须与 `training/data.py` 的 `condition` 逐项一致，否则模型会看到分布外的输入。
 * 十二维口径为：几何九项 + 目标三项，不含目标 z，也不含运行协议三项。
 */
object Inference {

    /** 截面等距变换；与 `accelerated/symmetry.py` 的 `VARIANTS` 逐项一致。 */
    private val VARIANTS = listOf(
        Triple(false, 1, 1), Triple(true, 1, 1), Triple(false, -1, 1), Triple(false, 1, -1),
        Triple(true, -1, 1), Triple(true, 1, -1), Triple(false, -1, -1), Triple(true, -1, -1),
    )

    /** 超出八视角后按概率采样的温度。 */
    private const val TEMPERATURE = 0.7

    /** 状态词表，与 `training/constants.py` 的 `STATES` 逐项对应；顺序不可改动。 */
    private val STATES: List<Pair<String, String>> = listOf(
        "air" to "positive_z",
        "slime_block" to "positive_z",
        "honey_block" to "positive_z",
        "redstone_block" to "positive_z",
        "iron_block" to "positive_z",
        "light_blue_glazed_terracotta" to "positive_z",
        "glass" to "positive_z",
        "piston" to "positive_x", "piston" to "negative_x",
        "piston" to "positive_y", "piston" to "negative_y",
        "piston" to "positive_z", "piston" to "negative_z",
        "sticky_piston" to "positive_x", "sticky_piston" to "negative_x",
        "sticky_piston" to "positive_y", "sticky_piston" to "negative_y",
        "sticky_piston" to "positive_z", "sticky_piston" to "negative_z",
        "observer" to "positive_x", "observer" to "negative_x",
        "observer" to "positive_y", "observer" to "negative_y",
        "observer" to "positive_z", "observer" to "negative_z",
    )

    /**
     * 生成候选。
     *
     * 前八个是确定性的截面变换视角，生成后按逆变换还原到用户原始坐标；超过八个的部分
     * 按温度采样，与服务器端的候选预算语义一致。
     */
    fun generate(task: JSONObject, count: Int, modelId: String, shouldCancel: () -> Boolean,
                 onProgress: (Int, Int) -> Unit): JSONArray {
        require(count in 1..64) { "候选数量必须在一至六十四之间" }
        val proposals = JSONArray()
        val volume = task.getInt("width") * task.getInt("height") * task.getInt("depth")
        // 大网格缩小批次，限制编码器与相对位置偏置的平方级内存。
        val batchLimit = (512 / volume).coerceIn(1, 4)
        while (proposals.length() < count) {
            if (shouldCancel()) throw CancellationException("已取消")
            val offset = proposals.length()
            val remaining = if (offset < VARIANTS.size) min(count, VARIANTS.size) - offset else count - offset
            val size = min(batchLimit, remaining)
            val variants = (offset until offset + size).map { VARIANTS[it % VARIANTS.size] }
            val requests = variants.map { (swap, sx, sy) -> GenerationInputs.build(task, swap, sx, sy) }
            val output = sample(requests, modelId, if (offset < VARIANTS.size) 0.0 else TEMPERATURE)
            if (shouldCancel()) throw CancellationException("已取消")
            for (index in requests.indices) {
                val (swap, sx, sy) = variants[index]
                val proposal = decode(requests[index], output.first, index * volume, output.second[index].toInt())
                proposals.put(GenerationInputs.restore(proposal, task, swap, sx, sy))
            }
            onProgress(proposals.length(), count)
        }
        return proposals
    }

    /** 同一批候选共享一次模型调用，随机候选显式传入采样温度。 */
    private fun sample(requests: List<GenerationInputs.Request>, modelId: String, temperature: Double): Pair<LongArray, LongArray> {
        val length = requests.first().grid.size
        val size = requests.size
        val features = FloatArray(size * length * GenerationInputs.COLUMNS)
        val coords = LongArray(size * length * 3)
        requests.forEachIndexed { index, request ->
            request.features.copyInto(features, index * request.features.size)
            request.coords.copyInto(coords, index * request.coords.size)
        }
        val value = Tensor.fromBlob(features, longArrayOf(size.toLong(), length.toLong(), GenerationInputs.COLUMNS.toLong()))
        val coord = Tensor.fromBlob(coords, longArrayOf(size.toLong(), length.toLong(), 3L))
        val padding = Tensor.fromBlobUnsigned(ByteArray(size * length), longArrayOf(size.toLong(), length.toLong()))
        val output = ModelLoader.require(modelId).runMethod("generate", IValue.from(value), IValue.from(coord),
            IValue.from(padding), IValue.from(temperature)).toTuple()
        val tokens = output[0].toTensor().dataAsLongArray
        val pushes = output[1].toTensor().dataAsLongArray
        check(tokens.size == size * length && pushes.size == size) { "模型返回的候选形状错误" }
        return tokens to pushes
    }

    /** 把一条 token 序列还原为变换后坐标系中的候选。 */
    private fun decode(request: GenerationInputs.Request, tokens: LongArray, offset: Int, push: Int): JSONObject {
        val length = request.grid.size
        check(push in 0 until length) { "模型返回的推动点越界" }
        val blocks = JSONArray()
        for (index in 0 until length) {
            val token = tokens[offset + index].toInt()
            check(token in STATES.indices) { "模型返回了词表外的方块" }
            if (token == 0) continue
            val (kind, facing) = STATES[token]
            val (x, y, z) = request.grid[index]
            blocks.put(JSONObject()
                .put("position", JSONObject().put("x", x).put("y", y).put("z", z))
                .put("block", JSONObject().put("kind", kind).put("facing", facing)))
        }
        val (pushX, pushY, pushZ) = request.grid[push.coerceIn(0, length - 1)]
        val proposal = JSONObject().put("blocks", blocks)
            .put("push", JSONObject().put("x", pushX).put("y", pushY).put("z", pushZ))
        return proposal
    }

    /** 负载摆放：目标首块在该列最前方方块前两格；与 `load_placement.align_targets` 一致。 */
    fun alignTargets(task: JSONObject, proposal: JSONObject): JSONObject {
        val fronts = HashMap<Pair<Int, Int>, Int>()
        val blocks = proposal.getJSONArray("blocks")
        for (index in 0 until blocks.length()) {
            val position = blocks.getJSONObject(index).getJSONObject("position")
            val key = position.getInt("x") to position.getInt("y")
            val z = position.getInt("z")
            fronts[key] = max(fronts[key] ?: z, z)
        }
        val aligned = JSONObject(task.toString())
        if (fronts.isEmpty()) return aligned
        val targets = aligned.getJSONArray("targets")
        for (index in 0 until targets.length()) {
            val target = targets.getJSONObject(index)
            val front = fronts[target.getInt("x") to target.getInt("y")] ?: continue
            target.put("z", front + 2)
        }
        return aligned
    }

    /** 调用原生判定层，不记录回放。 */
    fun judge(loadTask: JSONObject, proposal: JSONObject): JSONObject =
        JSONObject(NativeEngine.judge(request(loadTask, proposal, capture = false).toString()))

    /** 保存逐帧回放；只给选中的候选保存，避免手机存储被逐帧快照占满。 */
    fun saveReplay(context: Context, jobId: String, candidate: Int,
                   loadTask: JSONObject, proposal: JSONObject) {
        val result = JSONObject(NativeEngine.judge(request(loadTask, proposal, capture = true).toString()))
        ReplayStore.write(context, jobId, candidate, result.toString())
    }

    /** 组装判定请求。 */
    private fun request(loadTask: JSONObject, proposal: JSONObject, capture: Boolean): JSONObject =
        JSONObject()
            .put("task", loadTask)
            .put("proposal", proposal)
            .put("options", JSONObject().put("capture", capture).put("foundation", false))

    /** 状态词表，供结构导出使用。 */
    fun stateAt(token: Int): Pair<String, String>? =
        if (token in STATES.indices) STATES[token] else null
}
