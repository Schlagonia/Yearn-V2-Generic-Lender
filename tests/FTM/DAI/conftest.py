import pytest
from brownie import Wei, config

@pytest.fixture
def ftm_dai(interface):
    #ftm dai!
    yield interface.ERC20('0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E')

@pytest.fixture
def ftm_usdc(interface):
    #ftm usdc
    yield interface.ERC20('0x04068DA6C83AFCFA0e13ba15A6696662335D5B75')

@pytest.fixture
def scrUsdc(interface):
    yield interface.CErc20I("0xe45ac34e528907d0a0239ab5db507688070b20bf")

@pytest.fixture
def scrDai(interface):
    yield interface.CErc20I("0x8D9AED9882b4953a0c9fa920168fa1FDfA0eBE75")

@pytest.fixture
def gov(accounts):
    yield accounts[3]

@pytest.fixture
def whale(accounts, web3, chain, ftm_dai):
    
    acc = accounts.at("0x96d66427C18e12Ec77B5bC195c9Bf1D6d01B204a", force=True)
    
    yield acc

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
def vault(gov, rewards, guardian, ftm_dai, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = Vault.deploy({"from": guardian})
    vault.initialize(ftm_dai, gov, rewards, "", "")

    yield vault

@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    scrDai,
    scrUsdc,
    gov,
    Strategy,
    GenericScream,
):
    strategy = strategist.deploy(Strategy, vault)
    strategy.setKeeper(keeper)

    screamPlugin = strategist.deploy(GenericScream, strategy, "Scream", scrDai)
    strategy.addLender(screamPlugin, {"from": gov})
    assert strategy.numLenders() == 1
    yield strategy