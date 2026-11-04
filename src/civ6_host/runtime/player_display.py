"""Private candidate: response-bound display receipt/cache, no second transport.

The native internal v1 frame stays unchanged for Save, checkpoint comparison,
legality and provenance. The cache prepares a detached public v2 envelope only
when an exact receipt exists. No protocol request can select a formatter.
"""
from __future__ import annotations
from dataclasses import dataclass
import copy
import hashlib
import json
import re
import threading
from civ6_host.contracts import player_display as contract

PROVIDER_ID='official-owned-localization-toppanel-v1'
PROVIDER_SHA256='4a6da1b54eeb476a2259f9c47f822a19cc3a317c8da3b9910a78df6575bee249'


class DisplayUnavailable(RuntimeError):pass


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                   allow_nan=False,ensure_ascii=True).encode()).hexdigest()


def boundary(frame,locale):
    raw=contract.validate_raw(frame['observation'])
    if (type(frame.get('episode_id')) is not str or not frame['episode_id']
            or type(frame.get('game_generation')) is not str or not frame['game_generation']
            or type(frame.get('sequence')) is not int or frame['sequence']<0
            or type(locale) is not str or re.fullmatch('[a-z]{2}_[A-Z]{2}',locale) is None):
        raise ValueError('Invalid response/locale display identity')
    return (frame['episode_id'],frame['game_generation'],raw['player_id'],frame['sequence'],raw['turn'],
            locale,contract.SOURCE_SHA256,PROVIDER_ID,PROVIDER_SHA256)


@dataclass(frozen=True)
class _Receipt:
    owner:object
    serial:int
    identity:tuple
    response_sha256:str       # Administrative only; never included in public v2.
    raw_observation_sha256:str # Administrative only; never included in public v2.
    text:tuple
    origin:str


class _ReceiptIssuer:
    """Internal owned capability; instances/receipts are never wire values."""
    def __init__(self):
        self._thread=threading.get_ident();self._next=1;self._pending={}

    def _check(self):
        if threading.get_ident()!=self._thread:raise ValueError('Display provider crossed its owner thread')

    def _issue(self,frame,locale,text,origin):
        self._check();identity=boundary(frame,locale)
        if type(text) is not dict or set(text)!={'science','culture','faith'}:
            raise ValueError('Fixed provider did not return all TopPanel labels')
        # Validate the exact field-specific values before issuing the capability.
        contract.project_observation(frame['observation'],text)
        receipt=_Receipt(self,self._next,identity,_digest(frame),_digest(frame['observation']),
                         tuple(sorted(text.items())),origin)
        self._pending[self._next]=receipt;self._next+=1
        return receipt

    def consume(self,frame,locale,receipt):
        self._check()
        if (type(receipt) is not _Receipt or receipt.owner is not self
                or self._pending.get(receipt.serial) is not receipt):
            raise DisplayUnavailable('Missing, replaced or already consumed fixed-provider receipt')
        if (receipt.identity!=boundary(frame,locale) or receipt.response_sha256!=_digest(frame)
                or receipt.raw_observation_sha256!=_digest(frame['observation'])):
            raise DisplayUnavailable('Formatter receipt belongs to another exact response or locale')
        del self._pending[receipt.serial]
        return dict(receipt.text)

    def administrative(self,frame,locale):
        self._check();identity=boundary(frame,locale)
        return dict(schema='civ6-host.native-observation-administrative.v1',actor_channel=False,
            episode_id=identity[0],game_generation=identity[1],player_id=identity[2],sequence=identity[3],turn=identity[4],
            locale=locale,source_sha256=contract.SOURCE_SHA256,provider_id=PROVIDER_ID,provider_sha256=PROVIDER_SHA256,
            response_sha256=_digest(frame),raw_observation_sha256=_digest(frame['observation']),
            observation=copy.deepcopy(frame['observation']))


class NativeTopPanelIssuer(_ReceiptIssuer):
    def __init__(self,store=None):
        super().__init__()
        self._native_consumer=None
        if store is not None:
            from .player_display_toppanel import NativeTopPanelReceiptConsumer
            self._native_consumer=NativeTopPanelReceiptConsumer(store,self)

    def capture(self,frame,locale):
        from .player_display_toppanel import LOCALE
        if locale!=LOCALE or self._native_consumer is None:
            raise DisplayUnavailable('No exact native TopPanel formatter store/locale')
        return self._native_consumer.capture(frame)


class PublicDisplayCache:
    """Projection cache alongside SessionClient's existing raw response cache."""
    def __init__(self,issuer):
        if type(issuer) is not NativeTopPanelIssuer:
            raise ValueError('Display cache requires its fixed internal provider')
        self._issuer=issuer;self._rows={}

    def clear(self):self._rows.clear()

    def prepare(self,frame,locale,receipt,*,turn_mode='simultaneous'):
        # Prepare once; subsequent view()/information() calls copy this same
        # cached projection and cannot reuse the underlying formatter receipt.
        identity=boundary(frame,locale);key=identity[:5]
        if key in self._rows:raise DisplayUnavailable('This response already has its one display projection')
        decisions=frame.get('decisions')
        if type(decisions) is dict:
            if any(key in decisions for key in ('yield_display','treasury','research_progress')):
                raise DisplayUnavailable('Legacy raw sidecars require their existing typed public projectors')
            production=decisions.get('production_info')
            if type(production) is dict and any(type(row) is dict and 'raw' in row
                   for row in production.get('rows',())):
                raise DisplayUnavailable('Legacy raw production rows require their existing public projector')
        text=self._issuer.consume(frame,locale,receipt)
        outcome=frame['outcome']
        view=dict(schema=contract.PUBLIC_VIEW_SCHEMA,episode_id=frame['episode_id'],
            game_generation=frame['game_generation'],sequence=frame['sequence'],turn_mode=turn_mode,
            observation=contract.project_observation(frame['observation'],text),
            decisions=copy.deepcopy(frame.get('decisions')),applied_action=copy.deepcopy(frame.get('applied_action')),
            outcome={k:copy.deepcopy(outcome[k]) for k in ('terminated','truncated','reason')},
            locale=locale,display_source_sha256=contract.SOURCE_SHA256,
            display_scope=copy.deepcopy(contract.SCOPE),top_panel_text=text)
        contract.validate_public(view)
        for previous in list(self._rows):
            if previous[2] == key[2]:
                del self._rows[previous]
        self._rows[key]=(identity,_digest(frame),copy.deepcopy(view))
        return copy.deepcopy(view)

    def view(self,frame,locale):
        identity=boundary(frame,locale);cached=self._rows.get(identity[:5])
        if cached is None or cached[:2]!=(identity,_digest(frame)):
            raise DisplayUnavailable('No qualified display projection at this exact cached response')
        return copy.deepcopy(cached[2])

    def information(self,frame,locale):
        return contract.display_information(self.view(frame,locale))


def legacy_raw_copy(frame):
    """Offline migration/replay helper; no display-v2 label or schema is added."""
    contract.validate_raw(frame['observation'])
    return copy.deepcopy(frame)
