"""assert-text / assert-multi / assert-gone 独立命令。"""


def _cmd_assert_text(args):
    """独立命令：文本断言。"""
    from assertions.ui.pipeline import vts

    result = vts.locate_anchor(args.text, wait_sec=3)
    if result.get("found"):
        print(f"ASSERT-TEXT PASS: '{args.text}' 存在")
        return 0
    print(f"ASSERT-TEXT FAIL: '{args.text}' 未找到")
    return 1


def _cmd_assert_multi(args):
    """独立命令：批量文本断言。"""
    from assertions.ui.pipeline import vts

    results = []
    all_ok = True
    present_items = []
    for item in (args.present or []):
        present_items.extend(p.strip() for p in item.split(",") if p.strip())
    gone_items = []
    for item in (args.gone or []):
        gone_items.extend(g.strip() for g in item.split(",") if g.strip())

    for text in present_items:
        result = vts.locate_anchor(text, wait_sec=2)
        if result.get("found"):
            results.append(("present", text, "pass"))
            print(f"  ✅ [present] '{text}'")
        else:
            results.append(("present", text, "fail"))
            all_ok = False
            print(f"  ❌ [present] '{text}'")

    for text in gone_items:
        result = vts.locate_anchor_gone(text, wait_sec=2, max_retry=2)
        if result.get("gone"):
            results.append(("gone", text, "pass"))
            print(f"  ✅ [gone] '{text}'")
        else:
            results.append(("gone", text, "fail"))
            all_ok = False
            print(f"  ❌ [gone] '{text}'")

    total = len(results)
    passed = sum(1 for r in results if r[2] == "pass")
    print(f"ASSERT-MULTI {'PASS' if all_ok else 'FAIL'}: {passed}/{total} 通过")
    return 0 if all_ok else 1


def _cmd_assert_gone(args):
    """独立命令：文本消失断言。"""
    from assertions.ui.pipeline import vts

    result = vts.locate_anchor_gone(args.text, wait_sec=3, max_retry=2)
    if result.get("gone"):
        print(f"ASSERT-GONE PASS: '{args.text}' 已消失")
        return 0
    print(f"ASSERT-GONE FAIL: '{args.text}' 仍然存在")
    return 1