package com.mcscai.generator

import android.content.ContentValues
import android.content.Context
import android.provider.MediaStore
import org.json.JSONArray
import org.json.JSONObject

/**
 * 把候选导出为基岩版 `.mcstructure` 结构文件。
 *
 * 方块名与朝向编号的映射是服务器导入规则的反向：活塞用活塞专用的朝向编号，观察者的
 * 引擎朝向表示**输出端**，写回方块状态时要反回观察端。与 `training/web/mcstructure.py`
 * 逐项对应。
 *
 * 文件写到系统「下载」目录：用户需要用文件管理器或游戏把它取走，写进应用私有目录
 * 会对用户不可见。通过 Android 10 及以上的 MediaStore 写入公共下载目录。
 */
object StructureExport {

    /** 引擎方块类型 → 基岩版方块名。 */
    private val BLOCK_NAMES = mapOf(
        "slime_block" to "minecraft:slime",
        "honey_block" to "minecraft:honey_block",
        "piston" to "minecraft:piston",
        "sticky_piston" to "minecraft:sticky_piston",
        "redstone_block" to "minecraft:redstone_block",
        "observer" to "minecraft:observer",
        "iron_block" to "minecraft:iron_block",
        "light_blue_glazed_terracotta" to "minecraft:light_blue_glazed_terracotta",
        "glass" to "minecraft:glass",
    )

    /** 方块状态的朝向编号顺序；活塞与其它方块不同。 */
    private val DIRECTIONS = listOf(
        "negative_y", "positive_y", "negative_z", "positive_z", "negative_x", "positive_x",
    )
    private val PISTON_DIRECTIONS = listOf(
        "negative_y", "positive_y", "positive_z", "negative_z", "positive_x", "negative_x",
    )

    /** 需要写入朝向状态的方块种类。 */
    private val DIRECTED = setOf(
        "piston", "sticky_piston", "observer", "light_blue_glazed_terracotta",
    )

    /** 真实结构文件里每个调色板条目都带方块状态版本；读取端不使用，按当前值写入。 */
    private const val BLOCK_VERSION = 17959425

    /** 每个目标固定十块铁块负载。 */
    private const val LOAD_BLOCKS = 10

    /** 相反方向；`positive_z` 的对侧是 `negative_z`。 */
    private fun opposite(facing: String): String {
        val side = if (facing.startsWith("positive")) "negative" else "positive"
        return side + facing.substring(facing.indexOf('_'))
    }

    /** 引擎朝向 → 方块状态 `facing_direction` 的编号。 */
    private fun facingValue(kind: String, facing: String): Int {
        val table = if (kind == "piston" || kind == "sticky_piston") PISTON_DIRECTIONS else DIRECTIONS
        // 观察者的引擎朝向是输出端，写回结构时要反回到观察端。
        val value = if (kind == "observer") opposite(facing) else facing
        val index = table.indexOf(value)
        if (index < 0) throw IllegalArgumentException("$kind 的朝向无法写入结构：$facing")
        return index
    }

    /** 导出候选；`assembly` 为真时附带十块负载与外部推动器。返回写入的文件名。 */
    fun write(context: Context, jobId: String, candidate: Int, assembly: Boolean): String {
        val result = JobStore.result(context, jobId)
        val proposals = result.getJSONArray("proposals")
        if (candidate < 0 || candidate >= proposals.length()) throw IllegalArgumentException("候选不存在")
        val proposal = proposals.getJSONObject(candidate)

        val blocks = ArrayList<JSONObject>()
        val own = proposal.getJSONArray("blocks")
        for (index in 0 until own.length()) blocks.add(own.getJSONObject(index))

        if (assembly) {
            // 负载按本列最前方方块前两格摆放，与打标器和判定口径一致。
            val loadTasks = result.optJSONArray("load_tasks")
            val targets = if (loadTasks != null && candidate < loadTasks.length()) {
                loadTasks.getJSONObject(candidate).getJSONArray("targets")
            } else {
                result.getJSONObject("task").getJSONArray("targets")
            }
            for (index in 0 until targets.length()) {
                val target = targets.getJSONObject(index)
                for (offset in 0 until LOAD_BLOCKS) {
                    blocks.add(JSONObject()
                        .put("position", JSONObject()
                            .put("x", target.getInt("x"))
                            .put("y", target.getInt("y"))
                            .put("z", target.getInt("z") + offset))
                        .put("block", JSONObject().put("kind", "iron_block").put("facing", "positive_z")))
                }
            }
            val push = proposal.getJSONObject("push")
            blocks.add(JSONObject()
                .put("position", JSONObject()
                    .put("x", push.getInt("x"))
                    .put("y", push.getInt("y"))
                    .put("z", push.getInt("z") - 1))
                .put("block", JSONObject().put("kind", "piston").put("facing", "positive_z")))
        }

        val payload = structureBytes(blocks)
        val name = JobStore.read(context, jobId).let { JSONObject(it).getString("name") } +
            " · 候选${candidate + 1}" + (if (assembly) " · 十负载" else "") + ".mcstructure"
        save(context, name, payload)
        return name
    }

    /** 组装 `.mcstructure` 的二进制内容。 */
    fun structureBytes(blocks: List<JSONObject>): ByteArray {
        if (blocks.isEmpty()) throw IllegalArgumentException("这个候选没有可以导出的方块")

        // 包围盒与原点偏移：负坐标通过原点偏移记录，方块索引本身始终非负。
        var lowX = Int.MAX_VALUE; var lowY = Int.MAX_VALUE; var lowZ = Int.MAX_VALUE
        var highX = Int.MIN_VALUE; var highY = Int.MIN_VALUE; var highZ = Int.MIN_VALUE
        for (block in blocks) {
            val position = block.getJSONObject("position")
            val x = position.getInt("x"); val y = position.getInt("y"); val z = position.getInt("z")
            if (x < lowX) lowX = x; if (y < lowY) lowY = y; if (z < lowZ) lowZ = z
            if (x > highX) highX = x; if (y > highY) highY = y; if (z > highZ) highZ = z
        }
        val sizeX = highX - lowX + 1
        val sizeY = highY - lowY + 1
        val sizeZ = highZ - lowZ + 1

        // 方块索引按 x*(高*厚) + y*厚 + z 排列。
        val indices = IntArray(sizeX * sizeY * sizeZ) { -1 }
        val palette = LinkedHashMap<Pair<String, String>, Int>()
        val entries = ArrayList<Pair<String, String>>()
        for (block in blocks) {
            val spec = block.getJSONObject("block")
            val key = spec.getString("kind") to spec.getString("facing")
            val slot = palette.getOrPut(key) {
                entries.add(key)
                entries.size - 1
            }
            val position = block.getJSONObject("position")
            val index = (position.getInt("x") - lowX) * sizeY * sizeZ +
                (position.getInt("y") - lowY) * sizeZ + (position.getInt("z") - lowZ)
            indices[index] = slot
        }
        val empty = IntArray(indices.size) { -1 }

        val writer = NbtWriter()
        writer.writeRoot("") {
            int("format_version", 1)
            intList("size", listOf(sizeX, sizeY, sizeZ))
            intList("structure_world_origin", listOf(lowX, lowY, lowZ))
            compound("structure") {
                intListList("block_indices", listOf(indices.toList(), empty.toList()))
                emptyCompoundList("entities")
                compound("palette") {
                    compound("default") {
                        // 方块调色板：每个条目带名字、状态与状态版本。
                        layerList("block_palette", entries)
                        compound("block_position_data") { }
                    }
                }
            }
        }
        return writer.toByteArray()
    }

    /** 写入方块调色板列表。 */
    private fun NbtWriter.layerList(name: String, entries: List<Pair<String, String>>) {
        compoundListHeader(name, entries.size)
        for ((kind, facing) in entries) {
            compoundElement {
                string("name", BLOCK_NAMES[kind]
                    ?: throw IllegalArgumentException("暂不支持导出这种方块：$kind"))
                compound("states") {
                    if (kind in DIRECTED) int("facing_direction", facingValue(kind, facing))
                }
                int("version", BLOCK_VERSION)
            }
        }
    }

    /** 写出复合标签列表的表头。 */
    private fun NbtWriter.compoundListHeader(name: String, size: Int) {
        listHeaderFor(name, 10, size)
    }

    /** 把文件写到系统「下载」目录。 */
    private fun save(context: Context, name: String, payload: ByteArray) {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, name)
            put(MediaStore.Downloads.MIME_TYPE, "application/octet-stream")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IllegalStateException("无法写入下载目录")
        try {
            resolver.openOutputStream(uri)?.use { it.write(payload) }
                ?: throw IllegalStateException("无法写入下载目录")
            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            check(resolver.update(uri, values, null, null) == 1) { "无法完成下载文件写入" }
        } catch (error: Throwable) {
            // 写入失败时移除未完成条目，重试不会留下损坏或永久隐藏的文件。
            runCatching { resolver.delete(uri, null, null) }
            throw error
        }
    }
}
