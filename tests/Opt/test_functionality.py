import pytest
import brownie

from brownie import Wei

#Set is Incentivised
def test_set_ignorePrinting(
    plugin,
    gov,
    rando
):
    currentState = plugin.ignorePrinting()
    assert currentState == True
    opposite = not currentState
    plugin.setIgnorePrinting(opposite, {"from": gov})
    #Can assume if it doesnt return the original it returned the correct since its a boolean
    assert plugin.ignorePrinting() == opposite

    plugin.setIsIncentivised(currentState, {"from": gov})
    assert plugin.ignorePrinting() == currentState

    with brownie.reverts():
        plugin.setIsIncentivised(opposite, {"from": rando})


#set keeper
def test_set_keeper(
    plugin,
    gov,
    keeper,
    rando
):

    plugin.setKeep3r(keeper, {"from": gov})
    #Can assume if it doesnt return the original it returned the correct since its a boolean
    assert plugin.keep3r() == keeper

    with brownie.reverts():
        plugin.setKeep3r(keeper, {"from": rando})


def test_change_middle_token(
    plugin,
    gov,
    rando,
    router,
    router2,
    usdc,
    weth,
    strategist
):
    assert plugin.middleSwapToken() == usdc
    assert plugin.stable() == False

    plugin.setMiddleSwapToken(weth, False, {"from": strategist})

    assert plugin.middleSwapToken() == weth
    assert plugin.stable() == False

    plugin.setMiddleSwapToken(weth, True, {"from": strategist})

    assert plugin.middleSwapToken() == weth
    assert plugin.stable() == True

    #Should not be able to inject any other address
    with brownie.reverts():
        plugin.setMiddleSwapToken(rando, True, {"from": gov})


def test_manual_override(
    strategy, chain, vault, currency, interface, whale, strategist, gov, rando
):

    decimals = currency.decimals()

    deposit_limit = 100_000_000 * (10 ** decimals)
    vault.addStrategy(strategy, 9800, 0, 2 ** 256 - 1, 500, {"from": gov})

    amount1 = 50 * (10 ** decimals)
    currency.approve(vault, 2 ** 256 - 1, {"from": whale})
    currency.approve(vault, 2 ** 256 - 1, {"from": strategist})

    vault.setDepositLimit(deposit_limit, {"from": gov})
    assert vault.depositLimit() > 0

    amount2 = 50_000 * (10 ** decimals)

    vault.deposit(amount1, {"from": strategist})
    vault.deposit(amount2, {"from": whale})

    strategy.harvest({"from": strategist})

    status = strategy.lendStatuses()

    for j in status:
        plugin = interface.IGeneric(j[3])

        with brownie.reverts("!gov"):
            plugin.emergencyWithdraw(1, {"from": rando})
        with brownie.reverts("!management"):
            plugin.withdrawAll({"from": rando})
        with brownie.reverts("!management"):
            plugin.deposit({"from": rando})
        with brownie.reverts("!management"):
            plugin.withdraw(1, {"from": rando})

