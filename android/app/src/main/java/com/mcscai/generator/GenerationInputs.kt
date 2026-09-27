package com.mcscai.generator

import org.json.JSONArray
import org.json.JSONObject

/** 需求特征和八视角坐标转换；遍历顺序与服务器自回归推理保持一致。 */
object GenerationInputs {
    const val COLUMNS = 12

    /** 网格遍历顺序：每列从后向前，然后遍历截面；与 `serialization.positions` 一致。 */
    private fun grid(task: JSONObject): List<Triple<Int, Int, Int>> {
        val rows = ArrayList<Triple<Int, Int, Int>>()
        val width = task.getInt("width")
        val height = task.getInt("height")
        val depth = task.getInt("depth")
        for (x in 0 until width) {
            for (y in 0 until height) {
                for (z in -depth - 1 until -1) rows.add(Triple(x, y, z))
            }
        }
        return rows
    }

    /**
     * 一次生成所用的需求张量。
     *
     * `grid` 是本次生成实际使用的网格顺序（可能已被截面变换改写），`features` 与
     * `coords` 都是扁平数组，长度分别为 `grid.size * COLUMNS` 与 `grid.size * 3`。
     */
    class Request(val grid: List<Triple<Int, Int, Int>>, val features: FloatArray, val coords: LongArray)

    /** 构造十二维需求特征；口径与 `training/data.py` 的 `condition` 一致。 */
    fun build(task: JSONObject, swap: Boolean = false, sx: Int = 1, sy: Int = 1): Request {
        // 变换后的截面尺寸：交换会调换宽高，翻转不改变尺寸。
        val rawWidth = task.getInt("width")
        val rawHeight = task.getInt("height")
        val width = if (swap) rawHeight else rawWidth
        val height = if (swap) rawWidth else rawHeight
        val depth = task.getInt("depth")

        val targets = HashMap<Pair<Int, Int>, JSONObject>()
        val rows = task.getJSONArray("targets")
        for (index in 0 until rows.length()) {
            val row = rows.getJSONObject(index)
            // 目标同样参与截面变换，否则特征与网格会对不上。
            val px = if (swap) row.getInt("y") else row.getInt("x")
            val py = if (swap) row.getInt("x") else row.getInt("y")
            val nx = if (sx == 1) px else width - 1 - px
            val ny = if (sy == 1) py else height - 1 - py
            val moved = JSONObject(row.toString()).put("x", nx).put("y", ny)
            targets[nx to ny] = moved
        }

        // 自回归序列始终按变换后网格的 x/y/z 正序排列，与服务器 positions 一致。
        val transformed = grid(JSONObject(task.toString()).put("width", width).put("height", height))

        val features = FloatArray(transformed.size * COLUMNS)
        val coords = LongArray(transformed.size * 3)
        transformed.forEachIndexed { index, (x, y, z) ->
            val target = targets[x to y]
            val at = index * COLUMNS
            features[at + 0] = x / 8f
            features[at + 1] = y / 8f
            features[at + 2] = z / 8f
            features[at + 3] = width / 8f
            features[at + 4] = height / 8f
            features[at + 5] = depth / 8f
            features[at + 6] = (x + 0.5f) / width
            features[at + 7] = (y + 0.5f) / height
            features[at + 8] = (z + depth + 1f) / depth
            features[at + 9] = if (target != null) 1f else 0f
            features[at + 10] = if (target != null) target.getInt("order") / 4f else 0f
            features[at + 11] = targets.size / 8f
            coords[index * 3] = x.toLong()
            coords[index * 3 + 1] = y.toLong()
            coords[index * 3 + 2] = z.toLong()
        }
        return Request(transformed, features, coords)
    }

    /**
     * 逆变换：把生成结果还原到用户原始坐标。
     *
     * 正向变换是「先交换再翻转」，因此逆变换也必须先交换、并把两个翻转符号一起交换，
     * 与 `accelerated/symmetry.py` 的还原写法一致。
     */
    fun restore(proposal: JSONObject, task: JSONObject, swap: Boolean, sx: Int, sy: Int): JSONObject {
        val width = task.getInt("width")
        val height = task.getInt("height")
        val rx = if (swap) sy else sx
        val ry = if (swap) sx else sy

        fun restorePoint(x: Int, y: Int): Pair<Int, Int> {
            val px = if (swap) y else x
            val py = if (swap) x else y
            return (if (rx == 1) px else width - 1 - px) to
                (if (ry == 1) py else height - 1 - py)
        }

        val blocks = JSONArray()
        val rows = proposal.getJSONArray("blocks")
        for (index in 0 until rows.length()) {
            val row = rows.getJSONObject(index)
            val position = row.getJSONObject("position")
            val (x, y) = restorePoint(position.getInt("x"), position.getInt("y"))
            val spec = row.getJSONObject("block")
            val facing = restoreFacing(spec.getString("facing"), swap, rx, ry)
            blocks.put(JSONObject()
                .put("position", JSONObject().put("x", x).put("y", y).put("z", position.getInt("z")))
                .put("block", JSONObject().put("kind", spec.getString("kind")).put("facing", facing)))
        }
        val push = proposal.getJSONObject("push")
        val (pushX, pushY) = restorePoint(push.getInt("x"), push.getInt("y"))
        return JSONObject().put("blocks", blocks)
            .put("push", JSONObject().put("x", pushX).put("y", pushY).put("z", push.getInt("z")))
    }

    /** 朝向的逆变换；z 轴朝向在截面变换下不变。 */
    private fun restoreFacing(facing: String, swap: Boolean, rx: Int, ry: Int): String {
        val parts = facing.split("_")
        if (parts.size != 2) return facing
        var axis = parts[1]
        if (axis == "z") return facing
        if (swap) axis = if (axis == "x") "y" else "x"
        val sign = if (parts[0] == "positive") 1 else -1
        val flipped = sign * (if (axis == "x") rx else ry)
        return (if (flipped > 0) "positive_" else "negative_") + axis
    }

}
