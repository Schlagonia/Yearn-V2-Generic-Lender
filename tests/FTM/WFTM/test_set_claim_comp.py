from brownie import interface

def test_set_claim_comp(
    wftm,
    scrWftm,
    chain,
    whale,
    vault,
    strategy,
    accounts,
    fn_isolation,
    GenericScream,
    Contract,
):
    strategist = accounts.at(strategy.strategist(), force=True)
    gov = accounts.at(vault.governance(), force=True)
    currency = wftm

    currency.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    whale_deposit = 1_000_000 * 1e18
    vault.deposit(whale_deposit, {"from": whale})
    chain.sleep(10)
    chain.mine(1)
    strategy.setWithdrawalThreshold(0, {"from": gov})

    strategy.harvest({"from": strategist})
    scream_plugin = GenericScream.at(strategy.lenders(0))
    scream = Contract(scream_plugin.scream())
    unitroller = Contract(scream_plugin.unitroller())
    ctoken = Contract(scream_plugin.cToken())

    scream_plugin.setClaimComp(False, {"from": gov})

    for i in range(2):

        waitBlock = 25
        chain.mine(waitBlock)
        chain.sleep(waitBlock)
        scrWftm.mint(0,{"from": whale})
        strategy.harvest({"from": strategist})

    assert scream.balanceOf(scream_plugin) == 0
    interface.ComptrollerI(unitroller).claimComp(scream_plugin, [ctoken], {"from": scream_plugin})
    assert scream.balanceOf(scream_plugin) > 0
