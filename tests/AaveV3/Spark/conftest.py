import pytest
from brownie import Wei, config, Contract

@pytest.fixture
def dai():
    yield Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F")

@pytest.fixture
def adai():
    yield "0x4DEDf26112B3Ec8eC46e7E31EA5e123490B05B8B"

@pytest.fixture
def weth():
    yield "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

@pytest.fixture
def lendingPool():
    yield '0xC13e21B648A5Ee794902342038FF3aDAB66BE987'

@pytest.fixture
def router():
    yield '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F'

@pytest.fixture
def router2():
    yield "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"

@pytest.fixture
def gov(accounts):
    yield accounts[3]

@pytest.fixture
def whale(accounts):
    yield accounts.at("0xBA12222222228d8Ba445958a75a0704d566BF2C8", force=True)

@pytest.fixture
def rewards(gov):
    yield gov  # TODO: Add rewards contract

@pytest.fixture
def guardian(accounts):
    # YFI Whale, probably
    yield accounts[2]

@pytest.fixture
def strategist(accounts):
    # YFI Whale, probably
    yield accounts[2]

@pytest.fixture
def keeper(accounts):
    # This is our trusty bot!
    yield accounts[4]

@pytest.fixture
def rando(accounts):
    yield accounts[9]

@pytest.fixture
def realVault(pm):
    Vault = pm(config["dependencies"][0]).Vault
    realVault = Vault.at('0xdA816459F1AB5631232FE5e97a05BBBb94970c95')
    yield realVault

@pytest.fixture
def vault(gov, rewards, guardian, dai, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(dai, gov, rewards, "", "")
    vault.setDepositLimit(2**256-1, {"from": gov})

    yield vault

@pytest.fixture
def realStrategy(FtmStrategy):
    realStrategy = FtmStrategy.at('0x3280499298ACe3FD3cd9C2558e9e8746ACE3E52d')
    yield realStrategy

@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    gov,
    FtmStrategy,
):
    strategy = strategist.deploy(FtmStrategy, vault)
    strategy.setKeeper(keeper)

    assert strategy.numLenders() == 0
    yield strategy


@pytest.fixture
def v3Plugin(
    strategist,
    GenericAaveV3,
    strategy,
    weth,
    router,
    router2
):
    v3Plugin = strategist.deploy(
        GenericAaveV3, 
        strategy, 
        weth, 
        router,
        router2, 
        "Spark", 
        False
    )

    #assert v3Plugin.underlyingBalanceStored() == 0
    apr = v3Plugin.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = v3Plugin.aprAfterDeposit(5_000 * 1e18) # * 3154 * 10**4
    print(apr2/1e18)
    assert apr2 < apr
    yield v3Plugin


@pytest.fixture
def pluggedStrategy(
    strategy,
    v3Plugin,
    gov
):
    strategy.addLender(v3Plugin, {"from":gov})
    assert strategy.numLenders() == 1
    pluggedStrategy = strategy
    yield pluggedStrategy

@pytest.fixture
def pluggedVault(
    pluggedStrategy,
    vault,
    gov
):
    vault.addStrategy(pluggedStrategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    pluggedVault = vault
    yield pluggedVault
