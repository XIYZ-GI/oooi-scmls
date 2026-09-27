package com.mcscai.generator

import java.io.ByteArrayOutputStream

/**
 * 最小可用的基岩版小端 NBT 写入器。
 *
 * 只实现导出 `.mcstructure` 需要的几种标签类型，不追求覆盖 NBT 全貌。**字节序必须是小端**：
 * 基岩版结构文件是小端，而常见的 NBT 实现默认大端，写成大端会让游戏和项目的解析器
 * 都判定文件损坏。
 */
class NbtWriter {

    private val buffer = ByteArrayOutputStream()

    /** 标签类型编号，与 NBT 规范一致。 */
    private object Tag {
        const val END = 0
        const val INT = 3
        const val STRING = 8
        const val LIST = 9
        const val COMPOUND = 10
    }

    /** 写入有名字的复合标签作为根。 */
    fun writeRoot(name: String, body: NbtWriter.() -> Unit) {
        buffer.write(Tag.COMPOUND)
        writeStringRaw(name)
        body()
        buffer.write(Tag.END)
    }

    /** 写入一个 Int 字段。 */
    fun int(name: String, value: Int) {
        buffer.write(Tag.INT)
        writeStringRaw(name)
        writeIntRaw(value)
    }

    /** 写入一个 String 字段。 */
    fun string(name: String, value: String) {
        buffer.write(Tag.STRING)
        writeStringRaw(name)
        writeStringRaw(value)
    }

    /** 写入一个复合标签字段。 */
    fun compound(name: String, body: NbtWriter.() -> Unit) {
        buffer.write(Tag.COMPOUND)
        writeStringRaw(name)
        body()
        buffer.write(Tag.END)
    }

    /** 写入一个 Int 列表字段。 */
    fun intList(name: String, values: List<Int>) {
        listHeader(name, Tag.INT, values.size)
        for (value in values) writeIntRaw(value)
    }

    /** 写入一个「Int 列表的列表」字段，用于双层 `block_indices`。 */
    fun intListList(name: String, rows: List<List<Int>>) {
        listHeader(name, Tag.LIST, rows.size)
        for (row in rows) {
            // 列表元素的类型标记只写一次在表头，元素本身直接跟数据。
            writeIntRaw(row.size)
            for (value in row) writeIntRaw(value)
        }
    }

    /** 写入空的复合标签列表，用于 `entities`。 */
    fun emptyCompoundList(name: String) {
        listHeader(name, Tag.COMPOUND, 0)
    }

    /** 在列表上下文里写入一个复合标签元素（不带名字与类型标记）。 */
    fun compoundElement(body: NbtWriter.() -> Unit) {
        body()
        buffer.write(Tag.END)
    }

    /** 写入一个整数列表字段的表头，供列表元素复用。 */
    fun rawIntList(values: List<Int>) {
        writeIntRaw(values.size)
        for (value in values) writeIntRaw(value)
    }

    /** 写出列表字段的表头：类型标记、名字、元素类型、元素个数。 */
    private fun listHeader(name: String, elementType: Int, size: Int) {
        buffer.write(Tag.LIST)
        writeStringRaw(name)
        buffer.write(elementType)
        writeIntRaw(size)
    }

    /** 写出复合标签列表的表头；供结构导出拼装方块调色板使用。 */
    fun listHeaderFor(name: String, elementType: Int, size: Int) = listHeader(name, elementType, size)

    private fun writeStringRaw(value: String) {
        val bytes = value.toByteArray(Charsets.UTF_8)
        writeShortRaw(bytes.size)
        buffer.write(bytes, 0, bytes.size)
    }

    /** 小端 16 位整数。 */
    private fun writeShortRaw(value: Int) {
        buffer.write(value and 0xFF)
        buffer.write((value shr 8) and 0xFF)
    }

    /** 小端 32 位整数；写成大端会让结构文件不可读。 */
    private fun writeIntRaw(value: Int) {
        buffer.write(value and 0xFF)
        buffer.write((value shr 8) and 0xFF)
        buffer.write((value shr 16) and 0xFF)
        buffer.write((value shr 24) and 0xFF)
    }

    fun toByteArray(): ByteArray = buffer.toByteArray()
}
