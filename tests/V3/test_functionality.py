import pytest
import brownie

from brownie import Wei


#Set is Incentivised
def test_set_incentivized(
    v3Plugin,
    gov,
    rando
):
    currentState = v3Plugin.isIncentivised()
    opposite = not currentState
    v3Plugin.setIsIncentivised(opposite, {"from": gov})
    #Can assume if it doesnt return the original it returned the correct since its a boolean
    assert v3Plugin.isIncentivised() == opposite

    v3Plugin.setIsIncentivised(currentState, {"from": gov})
    assert v3Plugin.isIncentivised() == currentState

    with brownie.reverts():
        v3Plugin.setIsIncentivised(opposite, {"from": rando})


#set referral code
def test_referral_code(
    v3Plugin,
    gov,
    rando
):

    v3Plugin.setReferralCode('105', {"from": gov})
    #can assume if it dosent revert it works for non public varibale update

    with brownie.reverts():
        v3Plugin.setReferralCode('105', {"from": rando})

    with brownie.reverts():
        v3Plugin.setReferralCode('0', {"from": gov})


#set keeper
def test_set_keeper(
    v3Plugin,
    gov,
    keeper,
    rando
):

    v3Plugin.setKeep3r(keeper, {"from": gov})
    #Can assume if it doesnt return the original it returned the correct since its a boolean
    assert v3Plugin.keep3r() == keeper

    with brownie.reverts():
        v3Plugin.setKeep3r(keeper, {"from": rando})

