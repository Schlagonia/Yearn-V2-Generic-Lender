from brownie import Contract, Wei, reverts, ZERO_ADDRESS
import brownie
import pytest
import eth_utils
from Opt.useful_methods import deposit, sleep, close

from weiroll import WeirollPlanner, WeirollContract


def test_yswap(
    chain, pluggedVaultUsdc, pluggedStrategyUsdc, pluginUsdc, strategist,
    usdc, whaleUsdc, trade_factory, router, gov, ib, rando, whaleIb, cUsdc
):
    # Deposit to the vault
    plugin = pluginUsdc
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

    with reverts():
        plugin.manualClaimAndDontSell({"from": rando})

    plugin.setRewardStuff(plugin.minIbToSell(), 10, {"from": strategist})

    assert plugin.harvestTrigger("1") == True

    assert ib.balanceOf(plugin.address) == 0
    plugin.manualClaimAndDontSell({"from": strategist})
    assert ib.balanceOf(plugin.address) > 0
    chain.mine(1)
    #should not sell rewards
    plugin.harvest({"from": gov})

    assert ib.balanceOf(plugin.address) > 0
    token_in = ib
    token_out = token

    print(f"Executing trade...")
    receiver = plugin.address
    amount_in = token_in.balanceOf(plugin.address)
    assert amount_in > 0
    amount_out = 10e6
    usdc.transfer(trade_factory.address, amount_out, {"from": whaleUsdc})
    to_send = token_out.balanceOf(trade_factory.address)

    router = WeirollContract.createContract(Contract(plugin.router()))
    receiver = plugin
    token_out = WeirollContract.createContract(token)

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

    """
    planner.add(
        router.swapExactTokensForTokens(
            amount_in,
            0,
            route,
            receiver.address,
            2**256 - 1
        )
    )
    """
    #simulate a swap since there is currenty no liquidity for IB
    planner.add(
        token_out.transfer(
            plugin.address,
            to_send
        )
    )

    cmds, state = planner.plan()
    trade_factory.execute(cmds, state, {"from": "0x7Cd0A1A67B6aC5fC053d9b60C1E84592F248155b"})
    afterBal = usdc.balanceOf(plugin)
    print(usdc.balanceOf(plugin))

    assert afterBal > 0
    assert ib.balanceOf(plugin.address) == 0

    strategy.setWithdrawalThreshold(0, {"from":strategist})
    cUsdc.accrueInterest({"from": rando})
    tx = strategy.harvest({"from": strategist})
    print(tx.events)
    assert tx.events["Harvested"]["profit"] >= afterBal

    plugin.removeTradeFactoryPermissions({"from": strategist})
    assert plugin.tradeFactory() == ZERO_ADDRESS
    assert ib.allowance(plugin.address, trade_factory.address) == 0

    # withdrawal
    vault.withdraw({"from": user})
    assert (
        close(token.balanceOf(user), user_balance_before)
        or token.balanceOf(user) > user_balance_before
    )
