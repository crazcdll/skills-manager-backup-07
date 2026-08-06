from setuptools import setup

setup(
    name="mt-hotel-testdata-cli",
    version="0.1.9",
    description="酒店测试数据构造 CLI",
    author="zhaoshichuan",
    author_email="zhaoshichuan@meituan.com",
    python_requires=">=3.9",
    install_requires=["mt-qa-tool"],
    entry_points={
        "console_scripts": [
            "hotel-testdata=hotel_testdata_cli.cli.main:main",
        ],
    },
    # 包根映射：
    #   hotel_testdata_cli                          → ./
    #   含连字符的目录单独映射为合法 Python 包名（下划线）
    package_dir={
        "hotel_testdata_cli":                                        ".",
        # factory 含连字符子目录
        "hotel_testdata_cli.factory.non_room":                       "factory/non-room",
        "hotel_testdata_cli.factory.super_deal":                     "factory/super-deal",
        "hotel_testdata_cli.factory.super_deal_unified":             "factory/super-deal-unified",
        "hotel_testdata_cli.factory.audit.non_room":                 "factory/audit/non-room",
        "hotel_testdata_cli.factory.audit.super_deal":               "factory/audit/super-deal",
        "hotel_testdata_cli.factory.audit.super_deal_unified":       "factory/audit/super-deal-unified",
        # interface 含连字符子目录
        "hotel_testdata_cli.interface.non_room":                     "interface/non-room",
        "hotel_testdata_cli.interface.super_deal":                   "interface/super-deal",
        "hotel_testdata_cli.interface.super_deal_unified":           "interface/super-deal-unified",
    },
    packages=[
        "hotel_testdata_cli",
        "hotel_testdata_cli.scripts",
        "hotel_testdata_cli.factory",
        "hotel_testdata_cli.factory.fullday",
        "hotel_testdata_cli.factory.fullday.templates",
        "hotel_testdata_cli.factory.hourly",
        "hotel_testdata_cli.factory.hourly.templates",
        "hotel_testdata_cli.factory.infra",
        "hotel_testdata_cli.factory.ops",
        "hotel_testdata_cli.factory.audit",
        "hotel_testdata_cli.factory.audit.gift",
        "hotel_testdata_cli.factory.audit.package",
        "hotel_testdata_cli.factory.audit.non_room",
        "hotel_testdata_cli.factory.audit.super_deal",
        "hotel_testdata_cli.factory.audit.super_deal_unified",
        "hotel_testdata_cli.factory.inventory",
        "hotel_testdata_cli.factory.marketing",
        "hotel_testdata_cli.factory.non_room",
        "hotel_testdata_cli.factory.package",
        "hotel_testdata_cli.factory.super_deal",
        "hotel_testdata_cli.factory.super_deal_unified",
        "hotel_testdata_cli.routes",
        "hotel_testdata_cli.goods",
        "hotel_testdata_cli.cli",
        "hotel_testdata_cli.cli.commands",
        "hotel_testdata_cli.interface",
        "hotel_testdata_cli.interface.ops",
        "hotel_testdata_cli.interface.infra",
        "hotel_testdata_cli.interface.fullday",
        "hotel_testdata_cli.interface.non_room",
        "hotel_testdata_cli.interface.package",
        "hotel_testdata_cli.interface.super_deal",
        "hotel_testdata_cli.interface.super_deal_unified",
        "hotel_testdata_cli.interface.inventory",
        "hotel_testdata_cli.interface.marketing",
    ],
    package_data={
        # package_dir={"hotel_testdata_cli": "."} 时，key 须去掉顶层包名前缀
        # setuptools 会在 "." 下找 factory/fullday/templates/*.json
        "hotel_testdata_cli": [
            "factory/fullday/templates/*.json",
            "factory/hourly/templates/*.json",
            "factory/fullday/*.json",
            "factory/hourly/*.json",
            "factory/infra/*.json",
            "factory/marketing/*.json",
            "factory/ops/*.json",
            "factory/package/*.json",
        ],
        # 含连字符目录已通过 package_dir 映射为下划线包名，JSON 同样需要在映射后的包名下声明
        "hotel_testdata_cli.factory.non_room":           ["*.json"],
        "hotel_testdata_cli.factory.super_deal":         ["*.json"],
        "hotel_testdata_cli.factory.super_deal_unified": ["*.json"],
    },
    include_package_data=True,
)

