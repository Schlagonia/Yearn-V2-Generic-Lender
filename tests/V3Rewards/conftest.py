import pytest
from brownie import Wei, config, Contract

@pytest.fixture
def wavax():
    yield Contract("0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7")

@pytest.fixture
def usdc():
    yield Contract("0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E")

@pytest.fixture
def aWavax():
    yield "0x6d80113e533a2C0fe82EaBD35f1875DcEA89Ea97"

@pytest.fixture
def lendingPool():
    yield '0x794a61358D6845594F94dc1DB02A252b5b4814aD'

@pytest.fixture
def router():
    yield '0x60aE616a2155Ee3d9A68541Ba4544862310933d4'

@pytest.fixture
def gov(accounts):
    yield accounts[3]

@pytest.fixture
def whale(accounts):
    yield accounts.at("0xBBff2A8ec8D702E61faAcCF7cf705968BB6a5baB", force=True)

@pytest.fixture
def whaleUsdc(accounts):
    yield accounts.at("0xE195B82Df6A797551Eb1ACd506e892531824Af27", force=True)

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
def vault(gov, rewards, guardian, wavax, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(wavax, gov, rewards, "", "")
    vault.setDepositLimit(2**256-1, {"from": gov})

    yield vault

@pytest.fixture
def vaultUsdc(gov, rewards, guardian, usdc, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vaultUsdc = Vault.deploy({"from": guardian})
    vaultUsdc.initialize(usdc, gov, rewards, "", "")
    vaultUsdc.setDepositLimit(2**256-1, {"from": gov})

    yield vaultUsdc

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
def strategyUsdc(
    strategist,
    keeper,
    vaultUsdc,
    gov,
    FtmStrategy,
):
    strategyUsdc = strategist.deploy(FtmStrategy, vaultUsdc)
    strategyUsdc.setKeeper(keeper)

    assert strategyUsdc.numLenders() == 0
    yield strategyUsdc

@pytest.fixture
def v3Plugin(
    strategist,
    GenericAaveV3,
    strategy,
    wavax,
    router
):
    v3Plugin = strategist.deploy(
        GenericAaveV3, 
        strategy,
        wavax.address,
        router, 
        "AaveV3", 
        True
    )

    assert v3Plugin.underlyingBalanceStored() == 0
    apr = v3Plugin.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = v3Plugin.aprAfterDeposit(5_000 * 1e18) # * 3154 * 10**4
    print(apr2/1e18)
    assert apr2 < apr
    yield v3Plugin

@pytest.fixture
def v3PluginUsdc(
    strategist,
    GenericAaveV3,
    strategyUsdc,
    wavax,
    router
):
    v3PluginUsdc = strategist.deploy(
        GenericAaveV3, 
        strategyUsdc,
        wavax.address,
        router, 
        "AaveV3", 
        True
    )

    assert v3PluginUsdc.underlyingBalanceStored() == 0
    apr = v3PluginUsdc.apr()
    assert apr > 0
    print(apr/1e18)
    
    apr2 = v3PluginUsdc.aprAfterDeposit(5_000 * 1e18) # * 3154 * 10**4
    print(apr2/1e18)
    assert apr2 < apr
    yield v3PluginUsdc


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
def pluggedStrategyUsdc(
    strategyUsdc,
    v3PluginUsdc,
    gov
):
    strategyUsdc.addLender(v3PluginUsdc, {"from":gov})
    assert strategyUsdc.numLenders() == 1
    pluggedStrategyUsdc = strategyUsdc
    yield pluggedStrategyUsdc

@pytest.fixture
def pluggedVault(
    pluggedStrategy,
    vault,
    gov
):
    vault.addStrategy(pluggedStrategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    pluggedVault = vault
    yield pluggedVault

@pytest.fixture
def pluggedVaultUsdc(
    pluggedStrategyUsdc,
    vaultUsdc,
    gov
):
    vaultUsdc.addStrategy(pluggedStrategyUsdc, 10_000, 0, 2 ** 256 - 1, 1_000, {"from":gov})
    pluggedVaultUsdc = vaultUsdc
    yield pluggedVaultUsdc
