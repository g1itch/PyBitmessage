# -*- coding: utf-8 -*-

import base64

import stem
from stem.control import Controller


class OnionValidator(object):
    """Validation plugin for onion nodes"""
    def __init__(self):
        try:  # TODO: deal with authentication
            self.controller = Controller.from_port()
            self.controller.authenticate()
        except (stem.SocketError, stem.connection.AuthenticationFailure):
            raise ValueError  # do not load this if controller is not available

    def _validate_onion(self, addr):
        """Check the .onion address validity"""
        try:
            base64.b32decode(addr, True)
        except TypeError:
            return False

        if not self.controller:
            return True

        try:
            self.controller.get_hidden_service_descriptor(addr)
        except stem.DescriptorUnavailable:
            return False

        return True

    def __call__(self, node):
        """Filter check for .onion addresses validation"""
        addr = node.host
        try:
            addr, dom = addr.split('.')
        except ValueError:
            return True
        return self._validate_onion(addr) if dom == 'onion' else True


connect_plugin = OnionValidator()
