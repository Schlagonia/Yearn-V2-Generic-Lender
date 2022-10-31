from itertools import count
from brownie import Wei, reverts, Contract, interface, ZERO_ADDRESS
from useful_methods import genericStateOfVault, genericStateOfStrat
import random
import brownie
import pytest
from weiroll import WeirollPlanner, WeirollContract
executor_abi = [{"inputs":[{"internalType":"address","name":"governanceStrategy","type":"address"},{"internalType":"uint256","name":"votingDelay","type":"uint256"},{"internalType":"address","name":"guardian","type":"address"},{"internalType":"address[]","name":"executors","type":"address[]"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"address","name":"executor","type":"address"}],"name":"ExecutorAuthorized","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"address","name":"executor","type":"address"}],"name":"ExecutorUnauthorized","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"newStrategy","type":"address"},{"indexed":True,"internalType":"address","name":"initiatorChange","type":"address"}],"name":"GovernanceStrategyChanged","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"id","type":"uint256"}],"name":"ProposalCanceled","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"id","type":"uint256"},{"indexed":True,"internalType":"address","name":"creator","type":"address"},{"indexed":True,"internalType":"contract IExecutorWithTimelock","name":"executor","type":"address"},{"indexed":False,"internalType":"address[]","name":"targets","type":"address[]"},{"indexed":False,"internalType":"uint256[]","name":"values","type":"uint256[]"},{"indexed":False,"internalType":"string[]","name":"signatures","type":"string[]"},{"indexed":False,"internalType":"bytes[]","name":"calldatas","type":"bytes[]"},{"indexed":False,"internalType":"bool[]","name":"withDelegatecalls","type":"bool[]"},{"indexed":False,"internalType":"uint256","name":"startBlock","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"endBlock","type":"uint256"},{"indexed":False,"internalType":"address","name":"strategy","type":"address"},{"indexed":False,"internalType":"bytes32","name":"ipfsHash","type":"bytes32"}],"name":"ProposalCreated","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"id","type":"uint256"},{"indexed":True,"internalType":"address","name":"initiatorExecution","type":"address"}],"name":"ProposalExecuted","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"id","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"executionTime","type":"uint256"},{"indexed":True,"internalType":"address","name":"initiatorQueueing","type":"address"}],"name":"ProposalQueued","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"id","type":"uint256"},{"indexed":True,"internalType":"address","name":"voter","type":"address"},{"indexed":False,"internalType":"bool","name":"support","type":"bool"},{"indexed":False,"internalType":"uint256","name":"votingPower","type":"uint256"}],"name":"VoteEmitted","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"newVotingDelay","type":"uint256"},{"indexed":True,"internalType":"address","name":"initiatorChange","type":"address"}],"name":"VotingDelayChanged","type":"event"},{"inputs":[],"name":"DOMAIN_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"NAME","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"VOTE_EMITTED_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"__abdicate","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address[]","name":"executors","type":"address[]"}],"name":"authorizeExecutors","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"}],"name":"cancel","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"contract IExecutorWithTimelock","name":"executor","type":"address"},{"internalType":"address[]","name":"targets","type":"address[]"},{"internalType":"uint256[]","name":"values","type":"uint256[]"},{"internalType":"string[]","name":"signatures","type":"string[]"},{"internalType":"bytes[]","name":"calldatas","type":"bytes[]"},{"internalType":"bool[]","name":"withDelegatecalls","type":"bool[]"},{"internalType":"bytes32","name":"ipfsHash","type":"bytes32"}],"name":"create","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"}],"name":"execute","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"getGovernanceStrategy","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getGuardian","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"}],"name":"getProposalById","outputs":[{"components":[{"internalType":"uint256","name":"id","type":"uint256"},{"internalType":"address","name":"creator","type":"address"},{"internalType":"contract IExecutorWithTimelock","name":"executor","type":"address"},{"internalType":"address[]","name":"targets","type":"address[]"},{"internalType":"uint256[]","name":"values","type":"uint256[]"},{"internalType":"string[]","name":"signatures","type":"string[]"},{"internalType":"bytes[]","name":"calldatas","type":"bytes[]"},{"internalType":"bool[]","name":"withDelegatecalls","type":"bool[]"},{"internalType":"uint256","name":"startBlock","type":"uint256"},{"internalType":"uint256","name":"endBlock","type":"uint256"},{"internalType":"uint256","name":"executionTime","type":"uint256"},{"internalType":"uint256","name":"forVotes","type":"uint256"},{"internalType":"uint256","name":"againstVotes","type":"uint256"},{"internalType":"bool","name":"executed","type":"bool"},{"internalType":"bool","name":"canceled","type":"bool"},{"internalType":"address","name":"strategy","type":"address"},{"internalType":"bytes32","name":"ipfsHash","type":"bytes32"}],"internalType":"struct IAaveGovernanceV2.ProposalWithoutVotes","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"}],"name":"getProposalState","outputs":[{"internalType":"enum IAaveGovernanceV2.ProposalState","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getProposalsCount","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"},{"internalType":"address","name":"voter","type":"address"}],"name":"getVoteOnProposal","outputs":[{"components":[{"internalType":"bool","name":"support","type":"bool"},{"internalType":"uint248","name":"votingPower","type":"uint248"}],"internalType":"struct IAaveGovernanceV2.Vote","name":"","type":"tuple"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getVotingDelay","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"executor","type":"address"}],"name":"isExecutorAuthorized","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"}],"name":"queue","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"governanceStrategy","type":"address"}],"name":"setGovernanceStrategy","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"votingDelay","type":"uint256"}],"name":"setVotingDelay","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"},{"internalType":"bool","name":"support","type":"bool"}],"name":"submitVote","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"proposalId","type":"uint256"},{"internalType":"bool","name":"support","type":"bool"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"submitVoteBySignature","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address[]","name":"executors","type":"address[]"}],"name":"unauthorizeExecutors","outputs":[],"stateMutability":"nonpayable","type":"function"}]

def test_rewards(chain,
    usdc,
    whale,
    gov,
    strategist,
    rando,
    vault,
    Strategy,
    strategy,
    interface,
    GenericCompoundV3,
    gasOracle,
    strategist_ms,
    comp,
    cUsdc):

    starting_balance = usdc.balanceOf(strategist)
    currency = usdc
    decimals = currency.decimals()
    plugin = GenericCompoundV3.at(strategy.lenders(0))
    gasOracle.setMaxAcceptableBaseFee(10000 * 1e9, {"from": strategist_ms})

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale})
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 1_000_000_000 * (10 ** (decimals))
    debt_ratio = 10_000
    vault.addStrategy(strategy, debt_ratio, 0, 2 ** 256 - 1, 500, {"from": gov})
    vault.setDepositLimit(deposit_limit, {"from": gov})

    assert deposit_limit == vault.depositLimit()
    # our humble strategist deposits some test funds
    depositAmount = 501 * (10 ** (decimals))
    vault.deposit(depositAmount, {"from": strategist})

    assert strategy.estimatedTotalAssets() == 0
    chain.mine(1)
    assert strategy.harvestTrigger(1) == True

    strategy.harvest({"from": strategist})
    assert plugin.harvestTrigger(10) == False

    assert (
        strategy.estimatedTotalAssets() >= depositAmount * 0.999999
    )  # losing some dust is ok

    assert strategy.harvestTrigger(1) == False
    assert plugin.harvestTrigger(10) == False

    # whale deposits as well
    whale_deposit = 100_000 * (10 ** (decimals))
    vault.deposit(whale_deposit, {"from": whale})
    assert strategy.harvestTrigger(1000) == True
    assert plugin.harvestTrigger(10) == False
    strategy.harvest({"from": strategist})

    #Set uni fees
    plugin.setUniFees(3000, 500, {"from": strategist})

    #send come comp to the strategy
    toSend = 10 * (10 **18)
    comp.transfer(plugin.address, toSend, {"from": whale})
    assert comp.balanceOf(plugin.address) == toSend     
    assert plugin.harvestTrigger(10) == True
    chain.sleep(10)

    before_bal = plugin.underlyingBalanceStored()

    with brownie.reverts():
        plugin.harvest({"from": rando})

    plugin.harvest({"from": strategist})

    assert plugin.underlyingBalanceStored() > before_bal
    assert comp.balanceOf(plugin.address) == 0

    strategy.harvest({"from": strategist})
    status = strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )
    chain.sleep(6*3600)
    chain.mine(1)
    vault.withdraw({"from": strategist})

def test_no_rewards(
    usdc,
    Strategy,
    cUsdc,
    chain,
    whale,
    gov,
    strategist,
    rando,
    vault,
    strategy,
    GenericCompoundV3,
    aUsdc,
    comp
):
    starting_balance = usdc.balanceOf(strategist)
    currency = usdc
    decimals = currency.decimals()
    plugin = GenericCompoundV3.at(strategy.lenders(0))

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale})
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 1_000_000_000 * (10 ** (decimals))
    debt_ratio = 10_000
    vault.addStrategy(strategy, debt_ratio, 0, 2 ** 256 - 1, 500, {"from": gov})
    vault.setDepositLimit(deposit_limit, {"from": gov})

    assert deposit_limit == vault.depositLimit()
    # our humble strategist deposits some test funds
    depositAmount = 501 * (10 ** (decimals))
    vault.deposit(depositAmount, {"from": strategist})

    assert strategy.estimatedTotalAssets() == 0
    chain.mine(1)
    assert strategy.harvestTrigger(1) == True

    strategy.harvest({"from": strategist})
    assert plugin.harvestTrigger(10) == False

    assert (
        strategy.estimatedTotalAssets() >= depositAmount * 0.999999
    )  # losing some dust is ok

    assert strategy.harvestTrigger(1) == False
    assert plugin.harvestTrigger(10) == False

    # whale deposits as well
    whale_deposit = 100_000 * (10 ** (decimals))
    vault.deposit(whale_deposit, {"from": whale})
    assert strategy.harvestTrigger(1000) == True
    assert plugin.harvestTrigger(10) == False
    strategy.harvest({"from": strategist})

    assert plugin.harvestTrigger(10) == False
    assert plugin.getRewardsOwed() == 0
    assert plugin.getRewardAprForSupplyBase(plugin.getPriceFeedAddress(comp), 0) == 0

    #should still be able to call harvest
    plugin.harvest({"from": strategist})

def test_setter_functions(chain,
    usdc,
    whale,
    gov,
    strategist,
    GenericCompoundV3,
    rando,
    vault,
    strategy,
    accounts,
    cUsdc):
    #Check original values
    plugin = GenericCompoundV3.at(strategy.lenders(0))

    assert plugin.keep3r() == ZERO_ADDRESS
    assert plugin.minCompToSell() == .05 * (10**18)
    assert plugin.minRewardToHarvest() == 10 * (10 ** 18)
    assert plugin.ethToWantFee() == 0
    assert plugin.compToEthFee() == 0

    compEthFee = 3000
    ethWantFee = 100
    minComp = 10**20
    minReward = 10 ** 5

    with brownie.reverts():
        plugin.setKeep3r(accounts[1], {"from": rando})
    with brownie.reverts():
        plugin.setRewardStuff(minComp, minReward, {"from": rando})
    with brownie.reverts():
        plugin.setUniFees(compEthFee, ethWantFee, {"from": rando})

    plugin.setKeep3r(accounts[1], {"from": strategist})
    plugin.setRewardStuff(minComp, minReward, {"from": strategist})
    plugin.setUniFees(compEthFee, ethWantFee, {"from": strategist})

    assert plugin.keep3r() == accounts[1]
    assert plugin.minCompToSell() == minComp
    assert plugin.minRewardToHarvest() == minReward
    assert plugin.ethToWantFee() == ethWantFee
    assert plugin.compToEthFee() == compEthFee

    tx = plugin.cloneCompoundV3Lender(strategy, "Clone life gg", cUsdc, {"from": strategist})
    clone = GenericCompoundV3.at(tx.return_value)

    assert clone.keep3r() == ZERO_ADDRESS
    assert clone.minCompToSell() == .05 * (10**18)
    assert clone.minRewardToHarvest() == 10 * (10 ** 18)
    assert clone.ethToWantFee() == 0
    assert clone.compToEthFee() == 0

    with brownie.reverts():
        clone.setKeep3r(accounts[1], {"from": rando})
    with brownie.reverts():
        clone.setRewardStuff(minComp, minReward, {"from": rando})
    with brownie.reverts():
        clone.setUniFees(compEthFee, ethWantFee, {"from": rando})

    clone.setKeep3r(accounts[1], {"from": strategist})
    clone.setRewardStuff(minComp, minReward, {"from": strategist})
    clone.setUniFees(compEthFee, ethWantFee, {"from": strategist})

    assert clone.keep3r() == accounts[1]
    assert clone.minCompToSell() == minComp
    assert clone.minRewardToHarvest() == minReward
    assert clone.ethToWantFee() == ethWantFee
    assert clone.compToEthFee() == compEthFee

def test_trade_factory(chain,
    usdc,
    whale,
    gov,
    strategist,
    rando,
    vault,
    Strategy,
    strategy,
    interface,
    GenericCompoundV3,
    gasOracle,
    strategist_ms,
    trade_factory,
    weth,
    guardian,
    comp,
    cUsdc):

    starting_balance = usdc.balanceOf(strategist)
    currency = usdc
    decimals = currency.decimals()
    plugin = GenericCompoundV3.at(strategy.lenders(0))
    gasOracle.setMaxAcceptableBaseFee(10000 * 1e9, {"from": strategist_ms})

    usdc.approve(vault, 2 ** 256 - 1, {"from": whale})
    usdc.approve(vault, 2 ** 256 - 1, {"from": strategist})

    deposit_limit = 1_000_000_000 * (10 ** (decimals))
    debt_ratio = 10_000
    vault.addStrategy(strategy, debt_ratio, 0, 2 ** 256 - 1, 500, {"from": gov})
    vault.setDepositLimit(deposit_limit, {"from": gov})

    assert deposit_limit == vault.depositLimit()
    # our humble strategist deposits some test funds
    depositAmount = 501 * (10 ** (decimals))
    vault.deposit(depositAmount, {"from": strategist})

    assert strategy.estimatedTotalAssets() == 0
    chain.mine(1)
    assert strategy.harvestTrigger(1) == True

    strategy.harvest({"from": strategist})
    assert plugin.harvestTrigger(10) == False

    assert (
        strategy.estimatedTotalAssets() >= depositAmount * 0.999999
    )  # losing some dust is ok

    assert strategy.harvestTrigger(1) == False
    assert plugin.harvestTrigger(10) == False

    # whale deposits as well
    whale_deposit = 100_000 * (10 ** (decimals))
    vault.deposit(whale_deposit, {"from": whale})
    assert strategy.harvestTrigger(1000) == True
    assert plugin.harvestTrigger(10) == False
    strategy.harvest({"from": strategist})

    #send come comp to the strategy
    toSend = 10 * (10 **18)
    comp.transfer(plugin.address, toSend, {"from": whale})
    assert comp.balanceOf(plugin.address) == toSend     
    assert plugin.harvestTrigger(10) == True
    chain.sleep(1)

    before_bal = plugin.underlyingBalanceStored()

    plugin.harvest({"from": strategist})

    with reverts():
        plugin.setTradeFactory(trade_factory.address, {"from": rando})

    assert plugin.tradeFactory() == ZERO_ADDRESS
    plugin.setTradeFactory(trade_factory.address, {"from": gov})
    assert plugin.tradeFactory() == trade_factory.address

    assert plugin.harvestTrigger("1") == True

    plugin.harvest({"from": gov})

    #nothing should have been sold
    assert comp.balanceOf(plugin.address) == toSend  
    token_in = comp
    token_out = currency

    print(f"Executing trade...")
    receiver = plugin.address
    amount_in = token_in.balanceOf(plugin.address)
    assert amount_in > 0

    router = WeirollContract.createContract(Contract("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"))
    receiver = plugin

    planner = WeirollPlanner(trade_factory)
    token_in = WeirollContract.createContract(token_in)

    #token_bal_before = token.balanceOf(plugin)

    route = []
    if currency.symbol() == "WETH":
        route = [token_in.address, currency.address]
    else:
        route = [
            token_in.address, weth.address, currency.address
        ]

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
    assert comp.balanceOf(plugin.address) == 0

    plugin.removeTradeFactoryPermissions({"from": strategist})
    assert plugin.tradeFactory() == ZERO_ADDRESS
    assert comp.allowance(plugin.address, trade_factory.address) == 0

    strategy.harvest({"from": strategist})
    status = strategy.lendStatuses()
    form = "{:.2%}"
    formS = "{:,.0f}"
    for j in status:
        print(
            f"Lender: {j[0]}, Deposits: {formS.format(j[1]/1e6)}, APR: {form.format(j[2]/1e18)}"
        )
    chain.sleep(6*3600)
    chain.mine(1)
    vault.withdraw({"from": strategist})