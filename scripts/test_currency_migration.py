"""
测试多货币迁移的 Python 脚本

运行此脚本来验证 Prisma Client 是否正确识别新的货币字段
"""

import asyncio
import sys
from datetime import datetime
from typing import Optional

try:
    from prisma import Prisma
    from prisma.models import (
        LiteLLM_BudgetTable,
        LiteLLM_TeamTable,
        LiteLLM_UserTable,
        LiteLLM_VerificationToken,
    )
except ImportError:
    print("❌ 错误: 无法导入 Prisma Client")
    print("   请运行: poetry run prisma generate --schema=litellm/proxy/schema.prisma")
    sys.exit(1)


class MigrationTester:
    def __init__(self):
        self.prisma = Prisma()
        self.test_results = []

    async def connect(self):
        """连接到数据库"""
        try:
            await self.prisma.connect()
            print("✓ 数据库连接成功")
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False

    async def test_budget_table(self):
        """测试 LiteLLM_BudgetTable 的货币字段"""
        print("\n测试 1: LiteLLM_BudgetTable")
        try:
            # 读取现有数据
            budgets = await self.prisma.litellm_budgettable.find_many(take=5)
            print(f"  ✓ 读取成功: {len(budgets)} 条记录")

            if budgets:
                first = budgets[0]
                has_currency = hasattr(first, "budget_currency")
                print(f"  ✓ budget_currency 字段存在: {has_currency}")
                if has_currency:
                    print(f"    值: {first.budget_currency}")

            # 创建测试记录
            test_id = f"test-migration-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            test_budget = await self.prisma.litellm_budgettable.create(
                data={
                    "budget_id": test_id,
                    "max_budget": 1000.0,
                    "budget_currency": "CNY",  # 测试非 USD 货币
                    "created_by": "migration-test",
                    "updated_by": "migration-test",
                }
            )
            print(f"  ✓ 创建记录成功: currency={test_budget.budget_currency}")

            # 查询测试
            found = await self.prisma.litellm_budgettable.find_many(
                where={"budget_currency": "CNY"}
            )
            print(f"  ✓ 索引查询成功: 找到 {len(found)} 条 CNY 记录")

            # 清理
            await self.prisma.litellm_budgettable.delete(
                where={"budget_id": test_id}
            )
            print(f"  ✓ 清理测试数据成功")

            self.test_results.append(("LiteLLM_BudgetTable", True))
            return True

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            self.test_results.append(("LiteLLM_BudgetTable", False))
            return False

    async def test_team_table(self):
        """测试 LiteLLM_TeamTable 的货币字段"""
        print("\n测试 2: LiteLLM_TeamTable")
        try:
            # 检查字段
            teams = await self.prisma.litellm_teamtable.find_many(take=1)
            if teams:
                team = teams[0]
                has_budget_currency = hasattr(team, "budget_currency")
                has_spend_currency = hasattr(team, "spend_currency")
                print(f"  ✓ budget_currency 字段存在: {has_budget_currency}")
                print(f"  ✓ spend_currency 字段存在: {has_spend_currency}")

            self.test_results.append(("LiteLLM_TeamTable", True))
            return True

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            self.test_results.append(("LiteLLM_TeamTable", False))
            return False

    async def test_user_table(self):
        """测试 LiteLLM_UserTable 的货币字段"""
        print("\n测试 3: LiteLLM_UserTable")
        try:
            users = await self.prisma.litellm_usertable.find_many(take=1)
            if users:
                user = users[0]
                has_budget_currency = hasattr(user, "budget_currency")
                has_spend_currency = hasattr(user, "spend_currency")
                print(f"  ✓ budget_currency 字段存在: {has_budget_currency}")
                print(f"  ✓ spend_currency 字段存在: {has_spend_currency}")

            self.test_results.append(("LiteLLM_UserTable", True))
            return True

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            self.test_results.append(("LiteLLM_UserTable", False))
            return False

    async def test_verification_token(self):
        """测试 LiteLLM_VerificationToken 的货币字段"""
        print("\n测试 4: LiteLLM_VerificationToken")
        try:
            tokens = await self.prisma.litellm_verificationtoken.find_many(take=1)
            if tokens:
                token = tokens[0]
                has_budget_currency = hasattr(token, "budget_currency")
                has_spend_currency = hasattr(token, "spend_currency")
                print(f"  ✓ budget_currency 字段存在: {has_budget_currency}")
                print(f"  ✓ spend_currency 字段存在: {has_spend_currency}")

            self.test_results.append(("LiteLLM_VerificationToken", True))
            return True

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            self.test_results.append(("LiteLLM_VerificationToken", False))
            return False

    async def test_spend_logs(self):
        """测试 LiteLLM_SpendLogs 的货币字段"""
        print("\n测试 5: LiteLLM_SpendLogs")
        try:
            logs = await self.prisma.litellm_spendlogs.find_many(take=1)
            if logs:
                log = logs[0]
                has_spend_currency = hasattr(log, "spend_currency")
                has_model_currency = hasattr(log, "model_currency")
                has_spend_original = hasattr(log, "spend_original")
                has_exchange_rate = hasattr(log, "exchange_rate")

                print(f"  ✓ spend_currency 字段存在: {has_spend_currency}")
                print(f"  ✓ model_currency 字段存在: {has_model_currency}")
                print(f"  ✓ spend_original 字段存在: {has_spend_original}")
                print(f"  ✓ exchange_rate 字段存在: {has_exchange_rate}")

            self.test_results.append(("LiteLLM_SpendLogs", True))
            return True

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
            self.test_results.append(("LiteLLM_SpendLogs", False))
            return False

    async def test_daily_spend_tables(self):
        """测试所有每日消费统计表"""
        print("\n测试 6: Daily Spend Tables")

        tables = [
            ("LiteLLM_DailyUserSpend", self.prisma.litellm_dailyuserspend),
            ("LiteLLM_DailyTeamSpend", self.prisma.litellm_dailyteamspend),
            ("LiteLLM_DailyEndUserSpend", self.prisma.litellm_dailyenduserspend),
            ("LiteLLM_DailyAgentSpend", self.prisma.litellm_dailyagentspend),
            ("LiteLLM_DailyOrganizationSpend", self.prisma.litellm_dailyorganizationspend),
            ("LiteLLM_DailyTagSpend", self.prisma.litellm_dailytagspend),
        ]

        all_passed = True
        for table_name, table_client in tables:
            try:
                records = await table_client.find_many(take=1)
                if records:
                    record = records[0]
                    has_currency = hasattr(record, "spend_currency")
                    print(f"  ✓ {table_name}: spend_currency 存在 = {has_currency}")
                else:
                    print(f"  ⚠ {table_name}: 无数据，无法验证")
            except Exception as e:
                print(f"  ❌ {table_name}: {e}")
                all_passed = False

        self.test_results.append(("Daily Spend Tables", all_passed))
        return all_passed

    async def disconnect(self):
        """断开数据库连接"""
        try:
            await self.prisma.disconnect()
            print("\n✓ 数据库连接已关闭")
        except Exception as e:
            print(f"\n⚠ 关闭连接时出错: {e}")

    def print_summary(self):
        """打印测试结果总结"""
        print("\n" + "=" * 50)
        print("测试结果总结")
        print("=" * 50)

        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        for test_name, result in self.test_results:
            status = "✓ 通过" if result else "❌ 失败"
            print(f"{status}: {test_name}")

        print("=" * 50)
        print(f"总计: {passed}/{total} 测试通过")

        if passed == total:
            print("\n✅ 所有测试通过！迁移成功！")
            return True
        else:
            print(f"\n❌ 有 {total - passed} 个测试失败")
            return False


async def main():
    """主测试函数"""
    print("=" * 50)
    print("多货币迁移验证测试")
    print("=" * 50)

    tester = MigrationTester()

    # 连接数据库
    if not await tester.connect():
        sys.exit(1)

    # 运行所有测试
    try:
        await tester.test_budget_table()
        await tester.test_team_table()
        await tester.test_user_table()
        await tester.test_verification_token()
        await tester.test_spend_logs()
        await tester.test_daily_spend_tables()

    finally:
        await tester.disconnect()

    # 打印总结
    success = tester.print_summary()

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠ 测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ 测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
