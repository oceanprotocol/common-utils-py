#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

from ocean_keeper.utils import generate_multi_value_hash
from web3 import Web3

from ocean_utils.agreements.service_agreement import ServiceAgreement, ServiceTypes
from tests.resources.helper_functions import (
    get_ddo_sample,
    log_event
)
from tests.resources.tiers import e2e_test


@e2e_test
def test_escrow_access_secret_store_template_flow(setup_agreements_environment):
    """Test the agreement flow according to the EscrowAccessSecretStoreTemplate."""
    (
        keeper,
        publisher_acc,
        consumer_acc,
        agreement_id,
        asset_id,
        price,
        service_agreement,
        (lock_cond_id, access_cond_id, escrow_cond_id),

    ) = setup_agreements_environment

    print('creating agreement:'
          'agrId: ', agreement_id,
          'asset_id', asset_id,
          '[lock_cond_id, access_cond_id, escrow_cond_id]',
          [lock_cond_id, access_cond_id, escrow_cond_id],
          'tlocks', service_agreement.conditions_timelocks,
          'touts', service_agreement.conditions_timeouts,
          'consumer', consumer_acc.address,
          'publisher', publisher_acc.address
          )

    assert 'access' in keeper.template_manager.SERVICE_TO_TEMPLATE_NAME
    name = keeper.template_manager.SERVICE_TO_TEMPLATE_NAME.get('access')
    template_id = keeper.template_manager.create_template_id(name)
    assert keeper.template_manager.is_template_approved(template_id), 'Template is not approved.'
    assert keeper.did_registry.get_block_number_updated(asset_id) > 0, 'asset id not registered'
    success = keeper.agreement_manager.create_agreement(
        agreement_id,
        asset_id,
        template_id,
        [lock_cond_id, access_cond_id, escrow_cond_id],
        service_agreement.conditions_timelocks,
        service_agreement.conditions_timeouts,
        [consumer_acc.address, publisher_acc.address],
        consumer_acc
    )
    print('create agreement: ', success)
    assert success, f'createAgreement failed {success}'
    event = keeper.agreement_manager.subscribe_agreement_created(
        agreement_id,
        10,
        log_event(keeper.agreement_manager.AGREEMENT_CREATED_EVENT),
        (),
        wait=True
    )
    assert event, 'no event for AgreementCreated '

    # Verify condition types (condition contracts)
    agreement = keeper.agreement_manager.get_agreement(agreement_id)
    assert agreement.did == asset_id, ''
    template_values = keeper.template_manager.get_template(template_id)
    cond_types = template_values.condition_types
    for i, cond_id in enumerate(agreement.condition_ids):
        cond = keeper.condition_manager.get_condition(cond_id)
        assert cond.type_ref == cond_types[i]
        assert int(cond.state) == 1

    # Give consumer some tokens
    keeper.dispenser.request_vodkas(price, consumer_acc)
    # Fulfill lock_reward_condition
    pub_token_balance = keeper.token.get_token_balance(publisher_acc.address)
    starting_balance = keeper.token.get_token_balance(keeper.escrow_reward_condition.address)
    approved = keeper.token.token_approve(keeper.lock_reward_condition.address, price, consumer_acc)
    assert approved is True, 'token approval failed.'
    tx_hash = keeper.lock_reward_condition.fulfill(
        agreement_id, keeper.escrow_reward_condition.address, price, consumer_acc)
    keeper.lock_reward_condition.get_tx_receipt(tx_hash)
    event = keeper.lock_reward_condition.subscribe_condition_fulfilled(
        agreement_id,
        10,
        log_event(keeper.lock_reward_condition.FULFILLED_EVENT),
        (),
        wait=True
    )
    assert event, 'no event for LockRewardCondition.Fulfilled'
    assert keeper.condition_manager.get_condition_state(lock_cond_id) == 2, ''
    assert keeper.token.get_token_balance(
        keeper.escrow_reward_condition.address
    ) == (price + starting_balance), ''

    # Fulfill access_secret_store_condition
    tx_hash = keeper.access_secret_store_condition.fulfill(
        agreement_id, asset_id, consumer_acc.address, publisher_acc
    )
    keeper.access_secret_store_condition.get_tx_receipt(tx_hash)
    event = keeper.access_secret_store_condition.subscribe_condition_fulfilled(
        agreement_id,
        20,
        log_event(keeper.access_secret_store_condition.FULFILLED_EVENT),
        (),
        wait=True
    )
    assert event, 'no event for AccessSecretStoreCondition.Fulfilled'
    assert keeper.condition_manager.get_condition_state(access_cond_id) == 2, ''

    # Fulfill escrow_reward_condition
    tx_hash = keeper.escrow_reward_condition.fulfill(
        agreement_id, price, publisher_acc.address,
        consumer_acc.address, lock_cond_id,
        access_cond_id, publisher_acc
    )
    keeper.escrow_reward_condition.get_tx_receipt(tx_hash)
    event = keeper.escrow_reward_condition.subscribe_condition_fulfilled(
        agreement_id,
        10,
        log_event(keeper.escrow_reward_condition.FULFILLED_EVENT),
        (),
        wait=True
    )
    assert event, 'no event for EscrowReward.Fulfilled'
    assert keeper.condition_manager.get_condition_state(escrow_cond_id) == 2, ''
    assert keeper.token.get_token_balance(
        keeper.escrow_reward_condition.address
    ) == starting_balance, ''
    assert keeper.token.get_token_balance(publisher_acc.address) == (pub_token_balance + price), ''


@e2e_test
def test_agreement_hash():
    """
    This test verifies generating agreement hash using fixed inputs and ddo example.
    This will make it easier to compare the hash generated from different languages.
    """
    did = "did:op:0bc278fee025464f8012b811d1bce8e22094d0984e4e49139df5d5ff7a028bdf"
    template_id = '0x34219511357c43f4af90a4896b972a32809379bfbe8148eab3878e8406e75836'
    agreement_id = '0xf136d6fadecb48fdb2fc1fb420f5a5d1c32d22d9424e47ab9461556e058fefaa'
    ddo = get_ddo_sample()

    sa = ServiceAgreement.from_json(
        ddo.get_service(ServiceTypes.ASSET_ACCESS).as_dictionary())
    assert did == ddo.did
    # Don't generate condition ids, use fixed ids so we get consistent hash
    # (access_id, lock_id, escrow_id) = sa.generate_agreement_condition_ids(
    #     agreement_id, ddo.asset_id, consumer, publisher, keeper)
    access_id = '0x2d7c1d60dc0c3f52aa9bd71ffdbe434a0e58435571e64c893bc9646fea7f6ec1'
    lock_id = '0x1e265c434c14e668695dda1555088f0ea4356f596bdecb8058812e7dcba9ee73'
    escrow_id = '0xe487fa6d435c2f09ef14b65b34521302f1532ac82ba8f6c86116acd8566e2da3'
    print(f'condition ids: \n'
          f'{access_id} \n'
          f'{lock_id} \n'
          f'{escrow_id}')
    agreement_hash = ServiceAgreement.generate_service_agreement_hash(
        template_id,
        (access_id, lock_id, escrow_id),
        sa.conditions_timelocks,
        sa.conditions_timeouts,
        agreement_id,
        generate_multi_value_hash
    )
    print('agreement hash: ', agreement_hash.hex())
    expected = '0xc1bc6cdb161b9d04d5b48bceba51b9092c4da8db08003b96b93647fbe86e330c'
    print('expected hash: ', expected)
    assert agreement_hash.hex() == expected, 'hash does not match.'


def test_agreement():
    template_id = '0xda558ceb3abd482db04ea813810ae9c6cea5bf13ef9943908b1a8b51c4e56c7f'
    agreement_id = '0x' + ('e' * 64)
    access_id = '0x' + ('a' * 64)
    lock_id = '0x' + ('b' * 64)
    escrow_id = '0x' + ('c' * 64)

    signature = ServiceAgreement.generate_service_agreement_hash(
        template_id,
        [access_id, lock_id, escrow_id],
        [0, 0, 0],
        [0, 0, 0],
        agreement_id,
        generate_multi_value_hash
    )

    print({signature})
    assert (
        signature == Web3.toBytes(
            hexstr="0x3450be8127dbe156fad90956fd351df42ffcfabba89d230406a301ceb5b40f92"
        )), "The signature is not correct."
