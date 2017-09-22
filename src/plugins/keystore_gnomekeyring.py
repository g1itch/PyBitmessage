# -*- coding: utf-8 -*-

import gnomekeyring


class GnomeKeystore(object):

    def __init__(self, parent):
        self.keyring = gnomekeyring.get_default_keyring_sync() or 'login'
        self.parent = parent
        try:
            gnomekeyring.create_sync(self.keyring, None)
        except gnomekeyring.AlreadyExistsError:
            pass

    def fetch(self, address, key_type):
        try:
            keys = gnomekeyring.find_items_sync(
                gnomekeyring.ITEM_NETWORK_PASSWORD,
                {'protocol': 'bitmessage',
                 'address': address}
            )[0].secret
        except gnomekeyring.Error:
            return

        return keys.split(':')[
            0 if key_type == 'privencryptionkey' else 1]

    def push(self, address, keys):
        update = self.fetch(address, 'privencryptionkey') is not None
        try:
            gnomekeyring.item_create_sync(
                self.keyring,
                gnomekeyring.ITEM_NETWORK_PASSWORD,
                address,
                {'protocol': 'bitmessage',
                 'address': address},
                ':'.join(keys), update
            )
        except (gnomekeyring.DeniedError, gnomekeyring.CancelledError):
            pass

    def _fetch_password(self):
        try:
            items = gnomekeyring.find_items_sync(
                gnomekeyring.ITEM_GENERIC_SECRET,
                {'pybitmessage': 1}
            )
            return items[0].secret
        except gnomekeyring.Error:
            pass

    def _push_password(self, password):
        update = self._fetch_password() is not None
        try:
            gnomekeyring.item_create_sync(
                self.keyring,
                gnomekeyring.ITEM_GENERIC_SECRET,
                'PyBitmessage master password',
                {'pybitmessage': 1}, password, update
            )
        except (gnomekeyring.DeniedError, gnomekeyring.CancelledError):
            pass

    def decrypt(self, data):
        return self.parent._decrypt_AES_CFB(data, self._fetch_password())

    def encrypt(self, data):
        return self.parent._encrypt_AES_CFB(data, self._fetch_password())


connect_plugin = GnomeKeystore
