import pytest
import brownie
from useful_methods import deposit, sleep
from brownie import Wei, reverts


def test_harvest(
    pluggedVault,
    pluggedStrategy,
    plugin,
    gov,
    rando,
    weth,
    whale,
    chain,
    op,
    ib,
    whaleIb
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert plugin.hasAssets() == False
    assert plugin.nav() == 0
    #Deposit
    amount = Wei("50 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert plugin.hasAssets() == True
    assert plugin.nav() >= amount * .999
    assert plugin.nav() == plugin.underlyingBalanceStored()

    assert plugin.harvestTrigger("100000000") == False
    sleep(chain, 1)
    ib.transfer(plugin.address, 100e18, {"from": whaleIb})
    assert plugin.harvestTrigger("100000000") == True 
    

    with brownie.reverts():
        plugin.harvest({"from":rando})

    before_bal = plugin.underlyingBalanceStored()
    before_stake = plugin.stakedBalance()
    plugin.harvest({"from":gov})
    assert ib.balanceOf(plugin.address) == 0
    assert before_bal < plugin.underlyingBalanceStored()
    assert before_stake < plugin.stakedBalance()

"""
def test_harvest_usdc(
    pluggedVaultUsdc,
    pluggedStrategyUsdc,
    pluginUsdc,
    gov,
    rando,
    weth,
    usdc,
    whaleUsdc,
    chain,
    ib,
    whaleIb
):
    strategy = pluggedStrategyUsdc
    vault = pluggedVaultUsdc
    plugin = pluginUsdc

    assert plugin.hasAssets() == False
    assert plugin.nav() == 0
    #Deposit
    #amount = Wei("50 ether")
    amount = 1e12
    deposit(amount, whaleUsdc, usdc, vault)

    strategy.harvest({"from":gov})
    assert plugin.hasAssets() == True
    assert plugin.nav() >= amount * .999
    assert plugin.nav() == plugin.underlyingBalanceStored()

    assert plugin.harvestTrigger('100') == False
    sleep(chain, 1)
    ib.transfer(plugin.address, 100e18, {"from": whaleIb})
    assert plugin.harvestTrigger('100') == True

    with brownie.reverts():
        plugin.harvest({"from":rando})

    assert ib.balanceOf(plugin.address) == 0
    aBal = plugin.underlyingBalanceStored()
    plugin.harvest({"from":gov})
    #make sure the harvested was collected sold and reinvested 
    assert plugin.harvestTrigger('100') == False
    before_bal = plugin.underlyingBalanceStored()
    before_stake = plugin.stakedBalance()
    plugin.harvest({"from":gov})
    assert ib.balanceOf(plugin.address) == 0
    assert before_bal < plugin.underlyingBalanceStored()
    assert before_stake < plugin.stakedBalance()

    vault.withdraw({"from": whaleUsdc})
"""