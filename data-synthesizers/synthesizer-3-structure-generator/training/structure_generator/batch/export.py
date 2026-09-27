"""将已提交记录逐条导出压缩JSON数组，运行期间也可读取一致快照。"""

import argparse
import gzip
from pathlib import Path
import sqlite3


def export(database, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    count = 0
    try:
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
            with gzip.open(temporary, 'wt', encoding='utf-8') as stream:
                stream.write('[\n')
                for body, in db.execute('SELECT body FROM records ORDER BY rowid'):
                    if count:
                        stream.write(',\n')
                    stream.write(body)
                    count += 1
                stream.write('\n]\n')
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='输出路径，建议以.json.gz结尾')
    args = parser.parse_args()
    if args.database.resolve() == args.output.resolve():
        parser.error('导出文件不能覆盖数据库')
    print(f'已导出 {export(args.database, args.output)} 条结构：{args.output}')


if __name__ == '__main__':
    main()
