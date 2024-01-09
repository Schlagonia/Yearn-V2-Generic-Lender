import pytest
import brownie
from Spark.useful_methods import deposit, sleep, close
from brownie import Wei, reverts

#Strategy and Vault are imported after plugin has been plugged in
def test_logic(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    dai,
    whale,
    chain
):

    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, dai, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    deposit(amount, whale, dai, vault)
    apr = v3Plugin.apr()
    aprAfter = v3Plugin.aprAfterDeposit(amount)
    assert apr > aprAfter
    
    strategy.harvest({"from":gov})
    newApr = v3Plugin.apr()
    assert close(aprAfter, newApr)

    nav = v3Plugin.nav()
    sleep(chain, 10)    
    newNav = v3Plugin.nav()
    assert newNav > nav

    #withdraw Some
    daiBal = dai.balanceOf(whale.address)
    vault.withdraw(amount, {"from": whale})
    daiAfterBal = dai.balanceOf(whale.address)
    assert daiBal + amount <= daiAfterBal

    #check triggers with non incentivised
    trigger = v3Plugin.harvestTrigger('100')
    assert trigger == False

    # should be able to harvest even if not Incentivized
    v3Plugin.harvest({"from":gov})

    a = v3Plugin.apr()
    n = v3Plugin.nav()

    assert v3Plugin.weightedApr() ==  a * n

    #withdraw all
    daiBal = dai.balanceOf(whale.address)
    sleep(chain, 100)
    vault.withdraw({"from":whale})
    daiAfterBal = dai.balanceOf(whale.address)

    assert daiBal + amount <= daiAfterBal
   


def test_emergency_withdraw(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    whale,
    chain,
    dai
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, dai, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.emergencyWithdraw(v3Plugin.nav(), {"from":rando})

    daiBal = dai.balanceOf(gov.address)
    toWithdraw = amount * .1
    v3Plugin.emergencyWithdraw(toWithdraw, {"from":gov})
    daiBalAfter = dai.balanceOf(gov.address)
    assert daiBalAfter - toWithdraw == daiBal

    daiBal = dai.balanceOf(gov.address)
    nav = v3Plugin.nav()
    v3Plugin.emergencyWithdraw(nav, {"from":gov})
    daiBalAfter = dai.balanceOf(gov.address)
    assert daiBalAfter - nav == daiBal

def test__withdrawAll(
    pluggedVault,
    pluggedStrategy,
    v3Plugin,
    gov,
    rando,
    whale,
    chain,
    dai
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    #Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, dai, vault)

    strategy.harvest({"from":gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * .999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.withdrawAll({"from":rando})


    daiBal = dai.balanceOf(v3Plugin.address)
    v3Plugin.withdrawAll({"from":gov})
    
    assert v3Plugin.underlyingBalanceStored() == 0;
    assert dai.balanceOf(strategy.address) > daiBal
