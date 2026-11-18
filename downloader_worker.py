"""V5.1 media worker: durable history and clearer Instagram API diagnostics."""
import argparse
import heapq
import re
import sys
from datetime import timezone
from pathlib import Path

from download_history import open_history, has_post, record_post, import_old_codes, infer_existing_post, count_posts, has_story_item, record_story_item

import instaloader


def say(s):
    print(s, flush=True)


def safe_name(s):
    s = re.sub(r'[^\w .-]', '_', s, flags=re.UNICODE).strip(' .')
    return (s or 'Untitled')[:70]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('username')
    p.add_argument('--mode', choices=('all', 'new', 'latest'), default='new')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--types', required=True, help='comma-separated: feed,carousel,reels,stories,highlights')
    p.add_argument('--login-user', default='')
    args = p.parse_args()
    selected = set(args.types.split(','))
    if args.mode == 'all':
        args.limit = 0  # Full historical scan, independent of N
    allowed = {'feed', 'carousel', 'reels', 'stories', 'highlights'}
    if not selected or selected - allowed or not 0 <= args.limit <= 10000:
        p.error('类型或数量无效')

    folder = Path.cwd() / args.username
    folder.mkdir(parents=True, exist_ok=True)
    history = open_history(Path.cwd(), args.username)
    migrated = import_old_codes(history, folder)
    say(f'下载历史已加载：{count_posts(history)} 帖；本次导入旧记录 {migrated} 帖。')
    say('历史记录独立保存于 IG-Downloader/_download_history；即使删除媒体文件也不会自动重新下载。')
    loader = instaloader.Instaloader(
        dirname_pattern='{target}',
        download_pictures=True, download_videos=True,
        download_video_thumbnails=False, download_comments=False,
        save_metadata=False, post_metadata_txt_pattern='',
        max_connection_attempts=2,
    )
    if args.login_user:
        try:
            loader.load_session_from_file(args.login_user)
            if not loader.test_login():
                raise RuntimeError('会话已失效，请重新在 Terminal 登录 Instaloader')
            say(f'已加载 @{args.login_user} 的本机 Instaloader 会话。')
        except Exception as exc:
            say(f'错误：无法加载登录会话：{exc}')
            return 2
    elif {'stories', 'highlights'} & selected:
        say('错误：Stories 和 Highlights 需要登录会话。请先在 Terminal 运行 instaloader --login 你的IG用户名。')
        return 2

    say(f'开始 @{args.username} | 模式 {args.mode} | N={args.limit or "不限"} | 类型 {", ".join(sorted(selected))}')
    if args.mode == 'all':
        say('全部下载模式：遍历所选类型的全部可访问历史帖子；已在永久历史数据库记录的自动跳过（包括后来手动删除的文件）。')
    errors = []
    try:
        profile = instaloader.Profile.from_username(loader.context, args.username)
        if profile.is_private and not loader.context.is_logged_in:
            raise RuntimeError('此账号是私人账号；未登录无法访问')
    except Exception as exc:
        say(f'错误：无法读取主页：{exc}')
        say('诊断：Instagram 可能拒绝了第三方接口请求；HTTP 404 不一定代表账号不存在。')
        say('建议：确认 Instaloader >= 4.16；可在自己的 Mac 创建登录会话并填写页面的登录用户名，然后再尝试。')
        say('如反复出现 404/429，请先停止重试；不建议短时间频繁重复请求。')
        return 2

    # N counts checked posts in latest mode, newly saved posts in new mode.
    post_types = selected & {'feed', 'carousel', 'reels'}
    # Fast mode: check only N newest selected posts, skipping files already present.
    # Existing 'new' mode remains available for finding N undownloaded posts.
    if args.mode == 'latest' and args.limit < 1:
        say('错误：最新 N 帖模式要求 N 至少为 1。')
        return 2
    processed = 0
    inspected = 0
    skipped = 0
    if post_types:
        streams = []
        if {'feed', 'carousel'} & selected:
            try:
                streams.append(('主页帖子', iter(profile.get_posts())))
            except Exception as exc:
                errors.append(f'主页帖子初始化失败：{exc}')
        if 'reels' in selected:
            try:
                streams.append(('Reels', iter(profile.get_reels())))
            except Exception as exc:
                errors.append(f'Reels 初始化失败：{exc}')
        heap = []
        stopped = set()

        def advance(i):
            if i in stopped:
                return
            name, it = streams[i]
            try:
                post = next(it)
                ts = post.date_utc.replace(tzinfo=timezone.utc).timestamp()
                heapq.heappush(heap, (-ts, i, post))
            except StopIteration:
                stopped.add(i)
            except Exception as exc:
                stopped.add(i)
                errors.append(f'{name} 列表读取失败：{exc}')
                say(f'警告：{errors[-1]}')
                if name == 'Reels':
                    say('提示：Reels 列表不可访问；本次无法保证最新 N 帖包含所有 Reels。已记录的旧文件不会因此重新下载。')

        for i in range(len(streams)):
            advance(i)
        seen = set()
        while heap:
            _, i, post = heapq.heappop(heap)
            name = streams[i][0]
            code = post.shortcode
            if code not in seen:
                seen.add(code)
                is_carousel = post.typename == 'GraphSidecar'
                kind = 'carousel' if is_carousel else ('reels' if name == 'Reels' else 'feed')
                # A reel may also appear in the homepage feed; don't classify it
                # as a normal feed-only post if its video product type is Clips.
                if getattr(post, 'product_type', None) == 'clips':
                    kind = 'reels'
                if kind in selected:
                    inspected += 1
                    prefix = post.date_utc.strftime('%Y-%m-%d_%H-%M-%S_UTC')
                    known = has_post(history, code)
                    if not known:
                        # One-time migration from old Instaloader media. This cannot
                        # detect files deleted BEFORE upgrading; see README.
                        known = infer_existing_post(history, folder, code, prefix)
                        if known:
                            say(f'旧文件导入历史记录 {code} [{kind}]（日期推断，可能不完整）')
                    if known:
                        skipped += 1
                        say(f'跳过历史已记录帖子 {code} [{kind}]（即使文件已被手动删除）')
                    else:
                        say(f'下载新帖子 {processed + 1}{"/"+str(args.limit) if args.limit else ""}: {code} [{kind}]')
                        try:
                            loader.download_post(post, target=args.username)
                            # Only mark a post after the downloader reports success.
                            record_post(history, code, 'downloaded')
                            processed += 1
                        except Exception as exc:
                            errors.append(f'{code} 下载失败：{exc}')
                            say(f'错误：{errors[-1]}')
                    if args.mode == 'latest' and inspected >= args.limit:
                        say(f'已检查最新 {inspected} 帖（新下载 {processed} 帖，跳过 {skipped} 帖），立即停止向下查找。')
                        break
                    if args.mode != 'latest' and args.limit and processed >= args.limit:
                        say(f'达到 N={args.limit} 帖，结束帖子下载。')
                        break
            advance(i)
    say(f'帖子阶段结束：检查 {inspected} 帖，新下载 {processed} 帖，跳过历史帖子 {skipped} 帖。历史累计 {count_posts(history)} 帖。')
    say('Stories/Highlights 也保存独立历史记录；仅从本版成功执行之后开始可靠记录。')

    if 'stories' in selected:
        say('开始读取当前可访问 Stories（通常仅过去 24 小时）...')
        try:
            for story in loader.get_stories(userids=[profile.userid]):
                for item in story.get_items():
                    key = 'stories:' + str(item.mediaid)
                    if has_story_item(history, key):
                        say(f'跳过历史 Story {item.mediaid}')
                        continue
                    try:
                        loader.download_storyitem(item, f'{args.username}/Stories')
                        record_story_item(history, key)
                    except Exception as exc:
                        errors.append(f'Story 项目失败：{exc}')
                        say(f'警告：{errors[-1]}')
            say('Stories 阶段结束。')
        except Exception as exc:
            errors.append(f'Stories 读取失败：{exc}')
            say(f'警告：{errors[-1]}')

    if 'highlights' in selected:
        say('开始读取 Highlights...')
        try:
            for highlight in loader.get_highlights(profile):
                name = safe_name(highlight.title)
                # Unique ID prevents equal highlight names merging.
                target = f'{args.username}/Highlights/{name}_{highlight.unique_id}'
                for item in highlight.get_items():
                    key = 'highlights:' + str(highlight.unique_id) + ':' + str(item.mediaid)
                    if has_story_item(history, key):
                        say(f'跳过历史 Highlight {item.mediaid}')
                        continue
                    try:
                        loader.download_storyitem(item, target)
                        record_story_item(history, key)
                    except Exception as exc:
                        errors.append(f'Highlight {name} 项目失败：{exc}')
                        say(f'警告：{errors[-1]}')
            say('Highlights 阶段结束。')
        except Exception as exc:
            errors.append(f'Highlights 读取失败：{exc}')
            say(f'警告：{errors[-1]}')

    if errors:
        say(f'任务完成，但有 {len(errors)} 项错误/警告；部分媒体可能遗漏。')
        say('如果是 Instagram API 404/429，请核实 Instaloader 版本与登录会话；不要连续反复重试。')
        return 1
    say('任务完成：已检查所选类型的可访问内容。')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say('任务已中断。')
        sys.exit(130)
    except Exception as exc:
        say(f'任务失败：{type(exc).__name__}: {exc}')
        sys.exit(1)
