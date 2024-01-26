import pytest
import brownie
from V3.useful_methods import deposit, sleep, close
from brownie import Wei, reverts

# Strategy and Vault are imported after plugin has been plugged in
def test_logic(pluggedVault, pluggedStrategy, v3Plugin, gov, rando, wftm, whale, chain):

    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    # Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, wftm, vault)

    strategy.harvest({"from": gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * 0.999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    deposit(amount, whale, wftm, vault)
    apr = v3Plugin.apr()
    aprAfter = v3Plugin.aprAfterDeposit(amount)
    assert apr > aprAfter

    strategy.harvest({"from": gov})
    newApr = v3Plugin.apr()
    assert close(aprAfter, newApr)

    nav = v3Plugin.nav()
    sleep(chain, 10)
    newNav = v3Plugin.nav()
    assert newNav > nav

    # withdraw Some
    wftmBal = wftm.balanceOf(whale.address)
    vault.withdraw(amount, {"from": whale})
    wftmAfterBal = wftm.balanceOf(whale.address)
    assert wftmBal + amount <= wftmAfterBal

    # check triggers with non incentivised
    trigger = v3Plugin.harvestTrigger("100")
    assert trigger == False

    # should be able to harvest even if not Incentivized
    v3Plugin.harvest({"from": gov})

    a = v3Plugin.apr()
    n = v3Plugin.nav()

    assert v3Plugin.weightedApr() == a * n

    # withdraw all
    wftmBal = wftm.balanceOf(whale.address)
    sleep(chain, 100)
    vault.withdraw({"from": whale})
    wftmAfterBal = wftm.balanceOf(whale.address)

    assert wftmBal + amount <= wftmAfterBal


def test_emergency_withdraw(
    pluggedVault, pluggedStrategy, v3Plugin, gov, rando, whale, chain, wftm
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    # Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, wftm, vault)

    strategy.harvest({"from": gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * 0.999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.emergencyWithdraw(v3Plugin.nav(), {"from": rando})

    wftmBal = wftm.balanceOf(gov.address)
    toWithdraw = amount * 0.1
    v3Plugin.emergencyWithdraw(toWithdraw, {"from": gov})
    wftmBalAfter = wftm.balanceOf(gov.address)
    assert wftmBalAfter - toWithdraw == wftmBal

    wftmBal = wftm.balanceOf(gov.address)
    nav = v3Plugin.nav()
    v3Plugin.emergencyWithdraw(nav, {"from": gov})
    wftmBalAfter = wftm.balanceOf(gov.address)
    assert wftmBalAfter - nav == wftmBal


def test__withdrawAll(
    pluggedVault, pluggedStrategy, v3Plugin, gov, rando, whale, chain, wftm
):
    strategy = pluggedStrategy
    vault = pluggedVault

    assert v3Plugin.hasAssets() == False
    assert v3Plugin.nav() == 0
    # Deposit
    amount = Wei("500 ether")
    deposit(amount, whale, wftm, vault)

    strategy.harvest({"from": gov})
    assert v3Plugin.hasAssets() == True
    assert v3Plugin.nav() >= amount * 0.999
    assert v3Plugin.nav() == v3Plugin.underlyingBalanceStored()

    with brownie.reverts():
        v3Plugin.withdrawAll({"from": rando})

    wftmBal = wftm.balanceOf(v3Plugin.address)
    v3Plugin.withdrawAll({"from": gov})

    assert v3Plugin.underlyingBalanceStored() == 0
    assert wftm.balanceOf(strategy.address) > wftmBal
