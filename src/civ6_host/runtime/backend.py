"""Installed-code backend for the retained official Base/hotseat route.

Private resources still use their historical layout during migration. They are
data/proof inputs, never a Python import path. No model, reward or PPO is loaded.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def _prepare_runtime(resources, prepared_capture, private_resources):
    """Configure the same pinned private runtime for each native backend."""
    if os.name != 'nt':
        raise RuntimeError('The installed Windows GameCore requires Windows')
    path = Path(resources)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('An existing absolute private resource directory is required')
    root = path.resolve()
    existing = os.environ.get('CIV6_HOST_RESOURCE_ROOT')
    if existing is not None and Path(existing).resolve() != root:
        raise ValueError('Use a separate process for a different private resource root')
    if 'civ6_host.runtime.paths' in sys.modules and existing is None:
        raise RuntimeError('Resource paths were imported without configuration; restart required')
    os.environ['CIV6_HOST_RESOURCE_ROOT'] = str(root)
    from .resource_resolution import configure as configure_resources
    configure_resources(private_resources)
    if private_resources is not None and prepared_capture is None:
        raise ValueError('Relocated resources require an explicitly prepared capture')
    from .capture_admission import configure
    configure(prepared_capture)
    from .import_boundary import enable
    enable()
    from .paths import resource_root
    if resource_root() != root:
        raise ValueError('Private resource root differs')
    from .provenance import verify_installation
    return verify_installation()


class LocalHotseatBackend:
    """Model-independent adapter implementing the client's SessionBackend.

    All native options are explicit and forwarded unchanged. Limits and unknown
    options are validated by the extracted session. This factory does not claim
    simultaneous turns, a complete action catalogue or independent resource packaging.
    """
    def __init__(self, *, resources, official_bundle, ui_profile, prepared_capture=None, private_resources=None, public_view_players=None, **options):
        self.extraction = _prepare_runtime(resources, prepared_capture, private_resources)
        from .native.native_hotseat_session import NativeHotseatActionSession
        self._session=NativeHotseatActionSession(official_bundle=official_bundle,
            ui_profile=ui_profile,public_view_players=public_view_players,**options)

    def reset(self):return self._session.reset()
    def request(self,request):return self._session.request(request)
    def abort(self,reason='parent_abort'):return self._session.abort(reason)
    def close(self):return self._session.close()
    def read_player_view(self,response,player_id):
        reader=getattr(self._session,'read_player_view',None)
        if reader is None:raise ValueError('Public views are not enabled for this backend')
        return reader(response,player_id)

    @property
    def report(self):return getattr(self._session,'report',None)

    @property
    def run(self):return getattr(self._session,'run',None)

    @property
    def finished(self):return self._session.finished

    @property
    def last(self):return self._session.last


class NetworkBackend:
    """Installed-code adapter for the explicit captured LAN session."""

    def __init__(self, *, resources, official_bundle, prepared_capture=None,
                 private_resources=None, administrative_information=False,
                 public_display_diagnostic=False, public_display_source=None, **options):
        if type(administrative_information) is not bool:
            raise ValueError('administrative_information must be an exact Boolean')
        if official_bundle is None:
            raise ValueError('Network backend requires an exact captured official bundle')
        self.extraction = _prepare_runtime(resources, prepared_capture, private_resources)
        from .native.network_session import NativeNetworkSession
        if options.get('input_profile', 'lan') in ('xp1-lan','xp2-lan'):
            options['prepared_capture'] = prepared_capture
        if public_display_source is not None:
            options['public_display_source'] = public_display_source
        self._session = NativeNetworkSession(official_bundle=official_bundle,
            public_display_diagnostic=public_display_diagnostic, **options)
        self._display_projection_enabled = public_display_diagnostic
        self._administrative_information = administrative_information
        self._display_cache = self._display_issuer = None
        pins = {}
        self._information_store = None
        if administrative_information:
            if options.get('input_profile','lan') in ('xp1-lan','xp2-lan'):
                from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
                from .xp1_unit_attack_profile import precision_reference
                core_sha256=(XP2_CORE_SHA256 if options['input_profile']=='xp2-lan' else XP1_CORE_SHA256)
                pins={'combat':precision_reference(core_sha256)[1]}
                if core_sha256 == XP2_CORE_SHA256:
                    from .xp2_end_turn_readback import SOURCE
                    pins['turn_horizon'] = SOURCE[1]
            else:
                from .production_inputs import SOURCE as production_source
                from .city_growth import SOURCE as growth_source
                pins={'production':production_source[1],'growth':growth_source[1]}
        if public_display_diagnostic:
            pins['display'] = self._session.public_display_source
        if pins:
            from .information_store import InformationStore
            self._information_store = InformationStore(pins)
            self._session._information_store = self._information_store

    def reset(self):
        if self._information_store is not None:
            self._information_store.clear()
        if self._display_projection_enabled:
            from .player_display import NativeTopPanelIssuer, PublicDisplayCache
            self._display_issuer = NativeTopPanelIssuer(self._information_store)
            self._display_cache = PublicDisplayCache(self._display_issuer)
        return self._session.reset()
    def request(self, request):return self._session.request(request)
    def abort(self, reason='parent_abort'):return self._session.abort(reason)
    def close(self):return self._session.close()

    def read_administrative(self, group, response):
        """Read an explicitly enabled, response-bound native event snapshot."""
        self._session._owner()
        if not self._administrative_information or group == 'display':
            raise PermissionError('Backend administrative information group is unavailable')
        return self._information_store.read(group, response)

    def _read_player_display_projection(self, response):
        self._session._owner()
        if not self._display_projection_enabled or self._display_cache is None:
            raise ValueError('The fixed XP2 display diagnostic is unavailable')
        from .player_display import DisplayUnavailable
        from .player_display_toppanel import LOCALE
        try:
            return self._display_cache.view(response, LOCALE)
        except DisplayUnavailable:
            receipt = self._display_issuer.capture(response, LOCALE)
            return self._display_cache.prepare(response, LOCALE, receipt)

    @property
    def report(self):return getattr(self._session, 'report', None)

    @property
    def run(self):return getattr(self._session, 'run', None)

    @property
    def finished(self):return self._session.finished

    @property
    def last(self):return self._session.last

    @property
    def checkpoint(self):return self._session.saved_checkpoint
