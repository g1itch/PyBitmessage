# Copyright (c) 2019, Riverbank Computing Limited
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


from pyqtdeploy import ComponentBase, ComponentOption


class libffiComponent(ComponentBase):
    """The libffi component."""

    # The component options.
    options = [
        ComponentOption(
            'source', required=True,
            help="The archive containing the libffi source code."),
        ComponentOption(
            'static_msvc_runtime', type=bool,
            help="Set if the MSVC runtime should be statically linked."),
    ]

    def build(self, sysroot):
        """Build libffi for the target."""

        archive = sysroot.find_file(self.source)
        sysroot.unpack_archive(archive)

        sysroot.run(
            './configure', '--enable-static',
            '--prefix=' + sysroot.sysroot_dir)
        sysroot.run(sysroot.host_make)
        sysroot.run(sysroot.host_make, 'install')

    def configure(self, sysroot):
        """Complete the configuration of the component."""

        sysroot.verify_source(self.source)
