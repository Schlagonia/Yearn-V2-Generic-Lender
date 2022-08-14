import pytest
import brownie
from useful_methods import deposit, sleep
from brownie import Wei, reverts

def test_setup(
    v3Plugin,
    weth
):

    assert v3Plugin.isIncentivised() == True
    
    trigger = v3Plugin.harvestTrigger(100)
    assert trigger == False

def test_apr(
    v3Plugin,
    weth,
    aWeth,
    op
):
    liq = weth.balanceOf(aWeth)
    wethApr = v3Plugin._incentivesRate(liq, op.address)

    assert wethApr > 0


def test_harvest(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    weth,
    whale,
    chain,
    op
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("50 ether")
    deposit(amount, whale, weth, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    assert v3Plugin.harvestTrigger('100') == False
    sleep(chain, 1000)
    assert v3Plugin.harvestTrigger('100') == True

    with brownie.reverts():
        v3Plugin.harvest({"from":rando})

    aBal = v3Plugin.underlyingBalanceStored()
    v3Plugin.harvest({"from":gov})
    #make sure the harvested was collected sold and reinvested 
    assert v3Plugin.harvestTrigger('100') == False
    assert op.balanceOf(v3Plugin.address) == 0
    assert aBal < v3Plugin.underlyingBalanceStored()

def test_harvest_usdc(
    pluggedVaultUsdc,
    pluggedStrategyUsdc,
    v3PluginUsdc,
    gov,
    rando,
    weth,
    usdc,
    whaleUsdc,
    chain,
    op
):
    strategy = pluggedStrategyUsdc
    vault = pluggedVaultUsdc
    v3Plugin = v3PluginUsdc

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    #amount = Wei("50 ether")
    amount = 1e12
    deposit(amount, whaleUsdc, usdc, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    assert v3Plugin.harvestTrigger('100') == False
    sleep(chain, 1000)
    assert v3Plugin.harvestTrigger('100') == True

    with brownie.reverts():
        v3Plugin.harvest({"from":rando})

    assert op.balanceOf(v3Plugin.address) == 0
    aBal = v3Plugin.underlyingBalanceStored()
    v3Plugin.harvest({"from":gov})
    #make sure the harvested was collected sold and reinvested 
    assert v3Plugin.harvestTrigger('100') == False
    assert op.balanceOf(v3Plugin.address) == 0
    assert aBal < v3Plugin.underlyingBalanceStored()
