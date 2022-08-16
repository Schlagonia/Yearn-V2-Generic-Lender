from brownie import Contract, Wei, reverts, ZERO_ADDRESS
import brownie
import pytest
import eth_utils
from OptV3.useful_methods import deposit, sleep, close
from weiroll import WeirollPlanner, WeirollContract


def test_yswap(
    chain, pluggedVaultUsdc, pluggedStrategyUsdc, v3PluginUsdc, strategist,
    usdc, whaleUsdc, trade_factory, router, gov, op, rando
):
    # Deposit to the vault
    plugin = v3PluginUsdc
    strategy = pluggedStrategyUsdc
    vault = pluggedVaultUsdc
    token = usdc
    user = whaleUsdc
    user_balance_before = token.balanceOf(user)
    amount = 10_000e6
    deposit(amount, user, usdc, vault)

    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest({"from": strategist})
    assert close(plugin.nav(), amount)

    #sleep(chain, 3600)
    chain.sleep(3600)
    chain.mine(1)

    with reverts():
        plugin.setTradeFactory(trade_factory, {"from": rando})

    assert plugin.tradeFactory() == ZERO_ADDRESS
    plugin.setTradeFactory(trade_factory, {"from": gov})
    assert plugin.tradeFactory() == trade_factory

    assert plugin.harvestTrigger("1") == True

    plugin.harvest({"from": gov})

    token_in = op
    token_out = token

    print(f"Executing trade...")
    receiver = plugin.address
    amount_in = token_in.balanceOf(plugin.address)
    assert amount_in > 0

    router = WeirollContract.createContract(Contract(plugin.router()))
    receiver = plugin
    token_out = token

    planner = WeirollPlanner(trade_factory)
    token_in = WeirollContract.createContract(token_in)

    #token_bal_before = token.balanceOf(plugin)

    route = []
    if token.symbol() == "WETH" or token.symbol() == "USDC":
        route = [(token_in.address, token.address, False)]
    elif token.symbol() == "DAI":
        route = [
            (token_in.address, usdc.address, False),
            (usdc.address, token.address, True),
        ]
    else:
        pytest.skip("Unknown path")

    planner.add(
        token_in.transferFrom(
            plugin.address,
            trade_factory.address,
            amount_in,
        )
    )

    planner.add(
        token_in.approve(
            router.address,
            amount_in
        )
    )

    planner.add(
        router.swapExactTokensForTokens(
            amount_in,
            0,
            route,
            receiver.address,
            2**256 - 1
        )
    )

    cmds, state = planner.plan()
    trade_factory.execute(cmds, state, {"from": trade_factory.governance()})
    afterBal = token_out.balanceOf(plugin)
    print(token_out.balanceOf(plugin))

    assert afterBal > 0
    assert op.balanceOf(plugin.address) == 0

    strategy.setWithdrawalThreshold(0, {"from":strategist})

    tx = strategy.harvest({"from": strategist})
    print(tx.events)
    assert tx.events["Harvested"]["profit"] >= afterBal

    plugin.removeTradeFactoryPermissions({"from": strategist})
    assert plugin.tradeFactory() == ZERO_ADDRESS
    assert op.allowance(plugin.address, trade_factory.address) == 0

    # withdrawal
    vault.withdraw({"from": user})
    assert (
        close(token.balanceOf(user), user_balance_before)
        or token.balanceOf(user) > user_balance_before
    )

