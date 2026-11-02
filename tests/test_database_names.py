"""Database naming limits enforced by the affected Atlas shared cluster."""
from hashlib import sha256
import pytest
from authentication import tenant_database_name,principal_scope,PUBLIC_DEMO_PRINCIPAL
from persistence.mongo import _set_test_client,get_database
import mongomock


@pytest.mark.parametrize('base',['a','ab','abc','AURABI','aura_bi','a'*24])
@pytest.mark.parametrize('owner',[PUBLIC_DEMO_PRINCIPAL,'account-one','account-two'])
def test_all_supported_names_fit_atlas_38_byte_limit(base,owner):
    name=tenant_database_name(base,owner)
    assert len(name.encode('utf-8')) <= 38
    assert name.isascii()
    assert name==tenant_database_name(base,owner)


def test_valid_legacy_name_does_not_change():
    assert tenant_database_name('abc','existing-owner')=='abc_u_'+sha256(b'existing-owner').hexdigest()[:32]


def test_full_base_and_account_identity_both_separate_namespaces():
    names={tenant_database_name(base,owner) for base in ['AURABI','AUR_OTHER','AUR_OTHER_2'] for owner in [PUBLIC_DEMO_PRINCIPAL,'private-one','private-two']}
    assert len(names)==9


def test_reported_atlas_error_path_can_open_settings():
    # mongomock does not enforce Atlas's shorter limit; add that exact check at
    # the database boundary to reproduce the production failure without Atlas.
    class AtlasSizedClient(mongomock.MongoClient):
        def __getitem__(self,name):
            if len(name.encode('utf-8'))>38:
                raise AssertionError('Atlas database name exceeds 38 bytes')
            return super().__getitem__(name)
    _set_test_client(AtlasSizedClient(),'AURABI')
    with principal_scope(PUBLIC_DEMO_PRINCIPAL):
        db=get_database()
        db.settings.insert_one({'key':'demo','value':'ready'})
        assert db.settings.find_one({'key':'demo'})['value']=='ready'
        assert len(db.name.encode())==38
    with principal_scope('private-owner'):
        assert get_database().settings.find_one({'key':'demo'}) is None
