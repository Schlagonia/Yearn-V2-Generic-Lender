import pytest
from brownie import Wei, config, Contract

@pytest.fixture
def wftm():
    yield Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")

@pytest.fixture
def aWftm():
    yield "0x6d80113e533a2C0fe82EaBD35f1875DcEA89Ea97"

@pytest.fixture
def lendingPool():
    yield '0x794a61358D6845594F94dc1DB02A252b5b4814aD'

@pytest.fixture
def gov(accounts):
    yield accounts[3]

@pytest.fixture
def whale(accounts):
    yield accounts.at("0xc94A3Ff0bac12eeB9ff0CC4e08511E1FFaD6ba94", force=True)

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
    realVault = Vault.at('0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0')
    yield realVault

@pytest.fixture
def vault(gov, rewards, guardian, wftm, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(wftm, gov, rewards, "", "")
    vault.setDepositLimit(2**256-1, {"from": gov})

    yield vault

@pytest.fixture
def realStrategy(FtmStrategy):
    realStrategy = FtmStrategy.at('0x695A4a6e5888934828Cb97A3a7ADbfc71A70922D')
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
    strategy
):
    v3Plugin = strategist.deploy(GenericAaveV3, strategy, "AaveV3", False)
    assert v3Plugin.underlyingBalanceStored() == 0
    apr = v3Plugin.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = v3Plugin.aprAfterDeposit(500_000 * 1e18) # * 3154 * 10**4
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
