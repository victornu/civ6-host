"""One retained XP1 continuation capability on the existing loaded owner.

Shared operation methods use the real UI child, command transport and publisher.
This candidate capability is not public session admission or a substitute loader.
"""
from copy import deepcopy
from civ6_host.contracts import air_operations, archaeology, city_buildings, city_state_levies, great_people_actions, religious_unit_operations
from civ6_host.contracts import national_parks, rock_bands, unit_work
from civ6_host.contracts.unit_work import ADJACENT_KIND, ADJACENT_NETWORK_ACTION_FIELDS as UNIT_WORK_FIELDS
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256

READY='xp1-continuation-ready'
ACTIVE='xp1-continuation-active'

GOVERNOR_KINDS = ('appoint_governor', 'promote_governor', 'assign_governor', 'consider_governor_titles')
TRADE_KINDS = ('make_trade_route', 'change_trade_origin')
ESPIONAGE_KINDS = ('spy_travel', 'spy_mission', 'spy_cancel', 'spy_escape')
SPY_COMPLETION_KINDS = ('spy_renew', 'spy_completion_dismiss')
CONGRESS_KINDS = ('congress_open', 'congress_confirm_ballot', 'congress_confirm_proposals', 'congress_close')

def validate_command(action, *, observation=None, allow_faith=False):
    if type(allow_faith) is not bool:
        raise ValueError("Faith purchase admission flag must be Boolean")
    if type(action) is not dict:
        raise ValueError('Explicit command dictionary required')
    if action.get('kind') in CONGRESS_KINDS:
        from civ6_host.contracts.world_congress import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'confirm_dedications':
        from civ6_host.contracts.dedications import validate_action
        validate_action(action)
        return
    if action.get('kind') == city_buildings.GREAT_WORK_MOVE:
        city_buildings.validate_great_work_action(action)
        return
    if action.get('kind') == archaeology.KIND:
        archaeology.validate_action(action)
        return
    if action.get('kind') == archaeology.EXCAVATE:
        archaeology.validate_excavation(action, observation=observation)
        return
    if action.get('kind') == air_operations.KIND:
        air_operations.validate(action, observation)
        return
    if action.get('kind') == unit_work.BUILD_ROUTE:
        unit_work.validate_route(action, observation)
        return
    if action.get('kind') == national_parks.DESIGNATE:
        national_parks.validate_designation(action, observation)
        return
    if action.get('kind') == rock_bands.KIND:
        rock_bands.validate_action(action, observation)
        return
    if action.get('kind') in SPY_COMPLETION_KINDS:
        from civ6_host.contracts.spy_completion import validate_action
        if observation is None:
            raise ValueError('Spy completion command requires its exact player map dimensions')
        validate_action(action, observation['width'], observation['height'])
        return
    if action.get('kind') in ESPIONAGE_KINDS:
        from civ6_host.contracts.espionage import validate_action
        if observation is None:
            raise ValueError('Espionage command requires its exact player map dimensions')
        validate_action(action, observation['width'], observation['height'])
        return
    if action.get('kind') in TRADE_KINDS:
        from civ6_host.contracts import trade
        if observation is None:
            raise ValueError('Trade command requires its exact player map dimensions')
        validate = (trade.validate_route_action if action['kind'] == 'make_trade_route'
                    else trade.validate_origin_action)
        validate(action, observation['width'], observation['height'])
        return
    if action.get('kind') == 'diplomacy_initiate':
        from civ6_host.contracts.diplomacy_overview import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'world_war_response':
        from civ6_host.contracts.xp2_war_confirmation import validate_action
        validate_action(action)
        return
    if action.get('kind') in GOVERNOR_KINDS:
        from civ6_host.contracts.governors import validate_action
        validate_action(action)
        return
    if action.get('kind') in ('send_envoy', 'retain_envoys'):
        from civ6_host.contracts.envoys import validate_action
        validate_action(action)
        return
    if action.get('kind') == city_state_levies.ACTION:
        city_state_levies.validate_action(action)
        return
    if action.get('kind') in ('government','retain_government'):
        from civ6_host.contracts.government import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'policy_unlock':
        from civ6_host.contracts.policy_unlock import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'policies':
        from civ6_host.contracts.capability_policies import validate_explicit_action
        validate_explicit_action(action)
        return
    if action.get('kind') == 'purchase':
        from civ6_host.contracts.plot_purchases import validate_purchase_action
        validate_purchase_action(action, allow_faith=allow_faith)
        return
    if action.get('kind') == 'promote_unit':
        from civ6_host.contracts.unit_promotions import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'upgrade_unit':
        from civ6_host.contracts.unit_upgrades import validate_action
        validate_action(action)
        return
    if action.get('kind') in great_people_actions.KINDS:
        return great_people_actions.validate_action(action)
    if action.get('kind') == 'found_custom_religion':
        from civ6_host.contracts.religion_custom_names import validate_action
        return validate_action(action)
    if action.get('kind') == 'found_religion':
        from civ6_host.contracts.religion_founding import validate_action
        return validate_action(action)
    if action.get('kind') == 'activate_great_person':
        from civ6_host.contracts.great_person_activation import validate_action
        return validate_action(action)
    if action.get('kind') in religious_unit_operations.KINDS:
        return religious_unit_operations.validate_action(action)
    if action.get('kind') == 'activate_prophet':
        from civ6_host.contracts.prophet_activation import validate_action
        return validate_action(action)
    if action.get('kind') == 'add_belief':
        from civ6_host.contracts.religion_beliefs import validate_action
        return validate_action(action)
    if action.get('kind') == 'pantheon':
        from civ6_host.contracts.pantheon import validate_action
        validate_action(action)
        return
    if type(action.get('kind')) is str and action['kind'] in UNIT_WORK_FIELDS:
        from civ6_host.contracts.unit_work import validate_action
        validate_action(action)
        return
    from civ6_host.contracts.capability_world_input import WORLD_KINDS, validate_action as validate_world_action
    if action.get('kind') in WORLD_KINDS:
        validate_world_action(action)
        return
    if action.get('kind') in ('city_focus','city_citizen'):
        from civ6_host.contracts.capability_city_controls import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'unit_order':
        from civ6_host.contracts.capability_unit_orders import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'unit_formation':
        from civ6_host.contracts.unit_formations import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'district_range_attack':
        from civ6_host.contracts.city_ranged import district_validate_action
        district_validate_action(action)
        return
    if action.get('kind') == 'city_range_attack':
        from civ6_host.contracts.city_ranged import city_validate_action
        city_validate_action(action)
        return
    if action.get('kind') == 'unit_attack':
        from civ6_host.contracts.capability_unit_attacks import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'resolve_captured_city':
        from civ6_host.contracts.captured_city import validate_action
        validate_action(action)
        return
    if action.get('kind') in ('production_placement', 'production_resume'):
        from civ6_host.contracts.placement import validate_action
        validate_action(action)
        return
    if action.get('kind') in ('queue_append', 'queue_remove', 'queue_swap'):
        from civ6_host.contracts.production_queue import validate_action
        validate_action(action)
        return
    if action.get('kind') in ('end_turn','force_end_turn','unready_turn'):
        if set(action)!={'kind'}:raise ValueError('Turn request accepts only its explicit kind')
        return
    if action.get('kind') in ('research', 'civic', 'production'):
        from civ6_host.contracts.capability_choices import validate_action
        validate_action(action)
        return
    if action.get('kind')!='found_city' or set(action)!={'kind','unit_id','x','y'}:
        raise ValueError('This XP1 continuation family has no qualified adapter for the requested command')
    from civ6_host.contracts.capability_choices import validate_founder_action
    validate_founder_action(action)


def validate_unit_command(action):
    """Retained narrow diagnostic guard; shared session uses validate_command."""
    if type(action) is not dict or action.get('kind') != 'found_city':
        raise ValueError('Explicit foundation command required')
    validate_command(action)


def _purchase_allows_faith(continuation, session):
    """Select existing purchase admission for this retained saved owner.

    The purchase adapters still enforce the selected profile, city ownership,
    live source, fresh quote and native effect. This only carries their currency
    admission through the two preceding command-shape checks.
    """
    from .xp1_saved_load_owner import SavedLoadOwner
    if (type(session) is not SavedLoadOwner
            or session.continuation is not continuation
            or session.backend is not continuation.owner):
        return False
    core_sha256 = continuation.owner.load_abi.core_sha256
    return (core_sha256 == XP2_CORE_SHA256
            or core_sha256 == XP1_CORE_SHA256
            and getattr(session, 'xp1_faith_purchase', False) is True)


class SavedContinuation:
    def __init__(self,view):
        from .xp1_ui_binding import SavedPlayerView
        from .xp1_cache_publication import COMPLETED_STAGE
        from .xp1_action_transport import SavedActionTransport
        from .native.native_episode_identity import initialize_episode
        if type(view) is not SavedPlayerView or not view.completed:
            raise ValueError('Continuation requires the actual completed native UI view')
        b=view.owner;p=b.prefix;lease=view.publication.lease
        transport=getattr(p,'actions',None)
        if (b.destroyed or b.poisoned or b.busy or b.stage!=COMPLETED_STAGE
                or type(transport) is not SavedActionTransport or transport.backend is not b
                or lease.owner is not b or lease.prefix is not p or view.publication.owner is not b
                or b._xp1_player_view is not view or p.ui_child is not view.child
                or hasattr(b,'_xp1_continuation') or hasattr(lease,'continuation')
                or b.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
                or transport.transport_abi.core_sha256!=b.load_abi.core_sha256
                or view.core_sha256!=b.load_abi.core_sha256):
            raise ValueError('Continuation lacks its exact UI/command owners')
        lease._check_state(COMPLETED_STAGE,False)
        transport.require_empty_native_queue();b.control(empty=True)
        from .unit_operation_ui_profile import verify_live
        self.unit_source=verify_live(b.core._handle,b.runtime.read,core_sha256=b.load_abi.core_sha256)
        self.view,self.publication,self.lease=view,view.publication,lease
        self.owner,self.prefix,self.runtime,self.transport=b,p,p.runtime,transport
        self.publisher=p.view_publisher;self.ui_child=p.ui_child;self.game_child=p.game_child
        self.identity=initialize_episode(p)
        self.sequence=0;self.observation=deepcopy(view.result['observation'])
        self.explicit_production_snapshot=None
        self.explicit_world_input=None
        self.explicit_unit_orders=None
        self.explicit_production_queues=None
        self.trade_feedback=None
        self._xp1_production_queue_catalogue=None
        self.explicit_placements={}
        self.explicit_combat_units=None
        self.explicit_combat_cities=None
        self.explicit_captured_city=None
        self._xp1_unit_attack_catalogue=None
        self._xp1_placement_catalogue=None
        self.world_input_selections={};self.world_input_prompts={}
        self.emit=p.emit
        self.poisoned=False;self.publishing=False;self.publication_count=0
        b._xp1_continuation=self;lease.continuation=self;self.publisher._xp1_continuation=self
        b.stage=READY
        self.check(active=False)

    def check(self,*,active):
        b=self.owner;p=self.prefix
        if (type(active) is not bool or self.poisoned or b.destroyed or b.poisoned
                or b.stage!=(ACTIVE if active else READY) or b.busy is not active
                or b._xp1_continuation is not self
                or b.prefix is not p or p.runtime is not self.runtime
                or p.ui_child is not self.ui_child or p.game_child is not self.game_child
                or p.actions is not self.transport or self.transport.backend is not b
                or p.view_publisher is not self.publisher or self.publisher._xp1_continuation is not self
                or b._xp1_player_view is not self.view or not self.view.completed
                or self.view.owner is not b or self.view.publication is not self.publication
                or self.publication.owner is not b or self.publication.lease is not self.lease
                or self.lease.owner is not b or self.lease.prefix is not p
                or self.lease.continuation is not self or self.lease.publication_attempt is not self.publication
                or not self.lease.publication_finished or not self.publication.completed):
            raise ValueError('XP1 continuation lost its exact retained owners')
        self.lease._check_state(ACTIVE if active else READY,active)
        self.runtime.registry.validate(self.ui_child);self.runtime.registry.validate(self.game_child)
        from .native.native_episode_identity import require_episode
        if require_episode(p) is not self.identity:raise ValueError('XP1 continuation episode changed')

    def validate_publication(self,publisher):
        if publisher is not self.publisher or self.publishing:
            raise ValueError('XP1 continuation publication is foreign or reentrant')
        self.check(active=True)
        from .xp1_cache_publication import publication_target
        return publication_target(self.owner.load_abi.core_sha256)

    def before_publication(self,publisher):
        self.validate_publication(publisher);self.publishing=True

    def after_publication(self,publisher,dimensions):
        if publisher is not self.publisher or not self.publishing:
            raise ValueError('XP1 continuation publication return is out of order')
        self.check(active=True)
        if dimensions!=(self.observation['width'],self.observation['height'],
                       self.observation['width']*self.observation['height']):
            raise ValueError('XP1 continuation native map dimensions changed')
        self.prefix.deferred_events.drain()
        self.publishing=False;self.publication_count+=1

    def execute(self,action,*,session=None):
        validate_command(action, observation=getattr(self, 'observation', None),
                         allow_faith=_purchase_allows_faith(self, session))
        xp2 = self.owner.load_abi.core_sha256 == XP2_CORE_SHA256
        if (self.world_input_prompts.get(self.observation['player_id']) is not None
                and action['kind'] != 'world_war_response'):
            raise ValueError('The retained war modal requires an explicit response first')
        if action['kind'] == 'world_war_response':
            from .xp2_world_war import source_pin
            pin = getattr(session, 'war_source_sha256', None)
            if not xp2 or pin is None:
                raise ValueError('War responses require the explicitly selected XP2 session profile')
            source_pin(pin, 'xp2-lan')
        if action['kind'] in GOVERNOR_KINDS:
            if xp2:
                enabled = getattr(session, 'governors_diagnostic', False)
            else:
                enabled = getattr(session, 'xp1_governors_enabled', False)
            if enabled is not True:
                raise ValueError('Governors require their source-qualified expansion session')
        if action['kind'] == 'diplomacy_initiate' and (not xp2
                or getattr(session, 'diplomacy_overview_diagnostic', False) is not True):
            raise ValueError('Initial diplomacy requires the selected XP2 initial-choice group')
        if action['kind'] in TRADE_KINDS:
            flag = 'standard_trade' if xp2 else 'xp1_trade'
            standard = getattr(session, flag, False) is True and self.trade_feedback is None
            bbg = xp2 and getattr(session, 'trade_diagnostic', False) is True and self.trade_feedback is not None
            if not (standard or bbg):
                raise ValueError('Trade requires a selected native trade query group')
        if action['kind'] == 'unit_formation' and (not xp2 or getattr(session, 'unit_formations', False) is not True):
            raise ValueError('Formation commands require the selected stock XP2 query group')
        if action['kind'] == city_buildings.GREAT_WORK_MOVE:
            from .xp2_great_work_commands import enabled
            if session is None or not enabled(session):
                raise ValueError('Great Work commands require the selected expansion query group')
        if action['kind'] in (archaeology.KIND, archaeology.EXCAVATE):
            from .xp2_archaeology import commands_enabled
            if not xp2 or not commands_enabled(session):
                raise ValueError('Artifact choices require their admitted Gathering Storm owner')
        if action['kind'] == air_operations.KIND:
            from .xp2_air_operations import enabled
            if not xp2 or not enabled(session):
                raise ValueError('Air operations require their admitted Gathering Storm owner')
        if action['kind'] == unit_work.BUILD_ROUTE:
            from .xp2_build_route import enabled
            if not xp2 or not enabled(session):
                raise ValueError('Build Route requires its admitted Gathering Storm owner')
        if action['kind'] == national_parks.DESIGNATE:
            from .xp2_designate_park import enabled
            if not xp2 or not enabled(session):
                raise ValueError('Park designation requires its admitted Gathering Storm owner')
        if action['kind'] == rock_bands.KIND:
            from .xp2_rock_bands import enabled
            if not xp2 or not enabled(session):
                raise ValueError('Rock concerts require their admitted Gathering Storm owner')
        if action['kind'] == 'resolve_captured_city' and (
                getattr(self, 'captured_city_core', None) is not self.owner.core):
            raise ValueError('Captured-city commands require the retained expansion route')
        if action['kind'] == 'confirm_dedications':
            profile = 'stock_dedications' if xp2 else 'xp1_dedications_enabled'
            if getattr(session, profile, False) is not True:
                raise ValueError('Dedication commands require their source-qualified expansion query group')
        if action['kind'] in ESPIONAGE_KINDS + SPY_COMPLETION_KINDS and (not xp2 or self.trade_feedback is None
                or getattr(session, 'espionage_diagnostic', False) is not True):
            raise ValueError('Espionage requires the selected XP2 BBG espionage query group')
        if getattr(session, 'world_congress_diagnostic', False):
            from .xp2_world_congress import guard_other_action
            guard_other_action(session, action)
        if action['kind'] in CONGRESS_KINDS:
            stock_congress = (getattr(session, 'stock_dedications', False) is True
                              and getattr(session, 'world_congress_review_diagnostic', False) is True)
            if (not xp2 or getattr(session, 'world_congress_diagnostic', False) is not True
                    or stock_congress != (self.trade_feedback is None)):
                raise ValueError('Congress requires its selected XP2 profile and feedback owner')
        if action['kind'] == ADJACENT_KIND:
            from .xp2_lan_unit_work import primary_adjacent_enabled
            if not xp2 or not primary_adjacent_enabled(session):
                raise ValueError('Adjacent unit work requires the verified Gathering Storm owner')
        if not xp2 and action['kind'] in UNIT_WORK_FIELDS:
            from .xp1_unit_work_profile import require_owner
            require_owner(session)
        if not xp2 and action['kind'] in ('policies', 'government', 'retain_government'):
            if getattr(session, 'xp1_government', False) is not True:
                raise ValueError('Government and policies require the admitted Rise and Fall owner')
        if not xp2 and action['kind'] == 'purchase':
            flag = 'xp1_plot_purchase' if 'plot_id' in action else 'xp1_city_purchase'
            faith_allowed = flag == 'xp1_city_purchase' and getattr(session, 'xp1_faith_purchase', False) is True
            currencies = ('YIELD_GOLD', 'YIELD_FAITH') if faith_allowed else ('YIELD_GOLD',)
            if getattr(session, flag, False) is not True or action['currency'] not in currencies:
                raise ValueError('Purchase requires the admitted Rise and Fall owner and currency')
        if not xp2 and action['kind'] == 'promote_unit' and getattr(session, 'xp1_promotions', False) is not True:
            raise ValueError('Promotion requires the admitted Rise and Fall owner')
        if not xp2 and action['kind'] == 'upgrade_unit':
            if getattr(session,'xp1_unit_upgrades',False) is not True or action['resource_type'] is not None:
                raise ValueError('Unit upgrade requires the admitted Rise and Fall owner')
        if action['kind'] == 'found_custom_religion':
            if (xp2 or getattr(session,'xp1_religion_custom_names',False) is not True
                    or getattr(session,'xp1_religion_founding',False) is not True):
                raise ValueError('Custom religion naming requires its explicit Rise and Fall foundation group')
        if action['kind'] == 'found_religion':
            flag = 'xp2_religion_founding' if xp2 else 'xp1_religion_founding'
            if getattr(session,flag,False) is not True:
                raise ValueError('Religion founding requires its explicit expansion group')
        if action['kind'] in great_people_actions.KINDS:
            flag = 'xp2_great_people' if xp2 else 'xp1_great_people'
            if (getattr(session, flag + '_actions', False) is not True
                    or getattr(session, flag, False) is not True):
                raise ValueError('Great Person commands require the admitted expansion action owner')
            if (not xp2 and action['kind'] == great_people_actions.REJECT
                    and getattr(session, 'xp1_great_people_reject', False) is not True):
                raise ValueError('Great Person rejection requires its explicit Rise and Fall group')
        if action['kind'] == 'activate_great_person':
            from .xp1_great_person_activation import enabled
            if not enabled(session):
                raise ValueError('Great Person activation requires its explicit expansion group')
        if action['kind'] in religious_unit_operations.KINDS:
            flag = 'xp2_religious_unit_operations' if xp2 else 'xp1_religious_unit_operations'
            if getattr(session,flag,False) is not True:
                raise ValueError('Religious unit operations require their explicit expansion group')
        if action['kind'] == 'activate_prophet':
            flag = 'xp2_prophet_activation' if xp2 else 'xp1_prophet_activation'
            if getattr(session,flag,False) is not True:
                raise ValueError('Prophet activation requires its explicit expansion group')
        if action['kind'] == 'add_belief':
            flag = 'xp2_religion_beliefs' if xp2 else 'xp1_religion_beliefs'
            if getattr(session,flag,False) is not True:
                raise ValueError('Belief choice requires its explicit expansion group')
        if action['kind'] == 'pantheon':
            flag = 'xp2_pantheon' if xp2 else 'xp1_pantheon'
            if getattr(session,flag,False) is not True:
                raise ValueError('Pantheon requires its admitted expansion owner')
        if not xp2 and action['kind'] == 'policy_unlock':
            raise ValueError('Expansion command requires the verified XP2 route')
        if (not xp2 and action['kind'] in ('send_envoy', 'retain_envoys')
                and getattr(session, 'xp1_governors_enabled', False) is not True):
            raise ValueError('Envoy command requires the admitted Rise and Fall owner')
        if action['kind'] == city_state_levies.ACTION:
            flag = 'xp2_city_state_levies_enabled' if xp2 else 'xp1_governors_enabled'
            if getattr(session, flag, False) is not True:
                raise ValueError('Military levy requires its admitted expansion owner')
        if (xp2 and action['kind'] not in UNIT_WORK_FIELDS
                and action['kind'] not in TRADE_KINDS
                and action['kind'] not in ESPIONAGE_KINDS
                and action['kind'] not in SPY_COMPLETION_KINDS
                and action['kind'] not in CONGRESS_KINDS
                and action['kind'] not in great_people_actions.KINDS
                and action['kind'] not in religious_unit_operations.KINDS
                and action['kind'] not in (city_buildings.GREAT_WORK_MOVE, archaeology.KIND, archaeology.EXCAVATE,
                                           air_operations.KIND, unit_work.BUILD_ROUTE, national_parks.DESIGNATE,
                                           rock_bands.KIND)
                and action['kind'] not in ('activate_great_person','activate_prophet','found_religion','add_belief','pantheon')
                and action['kind'] not in GOVERNOR_KINDS and action['kind'] not in
                ('found_city','research','civic','production','end_turn','force_end_turn','unready_turn',
                 'world_select_unit','world_deselect_unit','world_plot_click','world_war_response','diplomacy_initiate','unit_order','unit_formation','confirm_dedications',
                 'queue_append','queue_remove','queue_swap','production_placement','production_resume','unit_attack','city_range_attack','district_range_attack','city_focus','city_citizen','purchase','promote_unit','upgrade_unit','policies','policy_unlock','government','retain_government','send_envoy','retain_envoys','resolve_captured_city',city_state_levies.ACTION)):
            raise ValueError('XP2 command family is not yet source-qualified in this session')
        return self._transition(action,session=session,pump=False)

    def flush_trade_feedback(self):
        if self.trade_feedback is None:
            raise ValueError('Native BBG trade feedback is not installed')
        return self.trade_feedback.flush()

    def advance(self,session):
        """One explicit native update through the same retained owner."""
        return self._transition(None,session=session,pump=True)

    def _transition(self,action,*,session,pump):
        """Explicit source-selected command. Missing families remain refused."""
        from time import perf_counter
        from .native.native_player_observation import observe_player
        from .saved_load_job_observer import require_quiescent
        from .xp1_load_capability import capability_source_scope
        is_turn=pump or action['kind'] in ('end_turn','force_end_turn','unready_turn')
        from civ6_host.contracts.capability_world_input import WORLD_KINDS
        is_war_response=not pump and action['kind']=='world_war_response'
        is_initial_diplomacy=not pump and action['kind']=='diplomacy_initiate'
        is_trade=not pump and action['kind'] in TRADE_KINDS
        is_espionage=not pump and action['kind'] in ESPIONAGE_KINDS
        is_spy_completion=not pump and action['kind'] in SPY_COMPLETION_KINDS
        is_congress_auto=not pump and action['kind']=='automatic_congress_empty_phase'
        is_congress=not pump and (action['kind'] in CONGRESS_KINDS or is_congress_auto)
        congress_turn=is_congress and (is_congress_auto or action['kind']=='congress_confirm_ballot')
        is_world=not pump and (action['kind'] in WORLD_KINDS or is_war_response)
        is_order=not pump and action['kind']=='unit_order'
        is_formation=not pump and action['kind']=='unit_formation'
        is_dedication=not pump and action['kind']=='confirm_dedications'
        is_queue=not pump and action['kind'] in ('queue_append','queue_remove','queue_swap')
        is_placement=not pump and action['kind'] in ('production_placement','production_resume')
        is_attack=not pump and action['kind']=='unit_attack'
        is_occupation=not pump and action['kind']=='resolve_captured_city'
        is_city_shot=not pump and action['kind'] in ('city_range_attack', 'district_range_attack')
        is_city=not pump and action['kind'] in ('city_focus','city_citizen')
        is_work=not pump and action['kind'] in UNIT_WORK_FIELDS
        is_purchase=not pump and action['kind']=='purchase'
        is_promotion=not pump and action['kind']=='promote_unit'
        is_upgrade=not pump and action['kind']=='upgrade_unit'
        is_pantheon=not pump and action['kind']=='pantheon'
        is_belief=not pump and action['kind']=='add_belief'
        is_religion_founding=not pump and action['kind']=='found_religion'
        is_religion_custom_names=not pump and action['kind']=='found_custom_religion'
        is_prophet_activation=not pump and action['kind']=='activate_prophet'
        is_great_person_activation=not pump and action['kind']=='activate_great_person'
        is_religious_unit_operation=not pump and action['kind'] in religious_unit_operations.KINDS
        is_great_people=not pump and action['kind'] in great_people_actions.KINDS
        is_great_work=not pump and action['kind']==city_buildings.GREAT_WORK_MOVE
        is_artifact_origin = not pump and action['kind'] == archaeology.KIND
        is_excavation = not pump and action['kind'] == archaeology.EXCAVATE
        is_air = not pump and action['kind'] == air_operations.KIND
        is_build_route = not pump and action['kind'] == unit_work.BUILD_ROUTE
        is_park_designation = not pump and action['kind'] == national_parks.DESIGNATE
        is_rock_concert = not pump and action['kind'] == rock_bands.KIND
        is_policy=not pump and action['kind'] in ('policies', 'policy_unlock')
        is_government=not pump and action['kind'] in ('government','retain_government')
        is_envoy=not pump and action['kind'] in ('send_envoy','retain_envoys')
        is_levy=not pump and action['kind']==city_state_levies.ACTION
        is_governor=not pump and action['kind'] in GOVERNOR_KINDS
        has_observation_effect = (is_world or is_order or is_formation or is_queue or is_placement or is_attack or is_occupation
                                  or is_city or is_city_shot or is_work or is_purchase or is_promotion
                                  or is_upgrade or is_policy or is_government or is_envoy or is_levy or is_governor
                                  or is_trade or is_espionage or is_spy_completion or is_congress
                                  or is_dedication or is_pantheon or is_belief or is_religion_founding
                                  or is_prophet_activation or is_great_person_activation or is_great_people or is_religion_custom_names
                                  or is_religious_unit_operation or is_great_work or is_artifact_origin
                                  or is_excavation or is_air or is_build_route or is_park_designation or is_rock_concert)
        if is_turn or has_observation_effect or is_initial_diplomacy:
            from .xp1_saved_load_owner import SavedLoadOwner
            if (type(session) is not SavedLoadOwner or session.continuation is not self
                    or session.backend is not self.owner or not session._running):
                raise ValueError('Native transition requires the actual active saved session')
        started = perf_counter()
        self.check(active=False)
        self.transport.require_empty_native_queue();self.owner.control(empty=True)
        b=self.owner;p=self.prefix;before_observation=deepcopy(self.observation)
        try:
            b.stage=ACTIVE;b.busy=True;self.check(active=True)
            before=b.jobs_snapshot('before');require_quiescent(before)
            before_scope = perf_counter()
            with capability_source_scope(b,'continuation'):
                scope_entered = perf_counter()
                kind='poll' if pump else action['kind'];pid=before_observation['player_id'];turn=before_observation['turn']
                effect=None
                if is_turn:
                    from .network_turns import advance,submit
                    from .xp1_turn_boundary import select
                    boundary=select(b.load_abi.core_sha256)
                    if pump:
                        advance(session,boundary=boundary)
                    else:
                        effect=submit(session,action,pid,boundary=boundary)
                elif is_war_response:
                    from .xp2_world_war import respond
                    effect=respond(session,action,before_observation)
                elif is_initial_diplomacy:
                    from .xp2_diplomacy_overview import initiate
                    effect=initiate(session,action,before_observation)
                elif is_trade:
                    from .xp2_trade import apply
                    effect=apply(session,action,before_observation)
                elif is_formation:
                    from .xp2_unit_formations import apply
                    effect=apply(session,action,before_observation)
                elif is_dedication:
                    from .xp2_dedications import apply
                    effect=apply(session,action,before_observation)
                elif is_espionage:
                    from .xp2_espionage import apply
                    effect=apply(session,action,before_observation)
                elif is_congress:
                    from .xp2_world_congress import apply, advance_empty_phase
                    effect = (advance_empty_phase(session, before_observation) if is_congress_auto
                              else apply(session, action, before_observation))
                elif is_spy_completion:
                    from .xp2_spy_completion import apply
                    effect=apply(session,action,before_observation)
                elif is_world:
                    from .xp1_world_input import apply
                    effect=apply(session,action,before_observation)
                elif is_work:
                    from .native.native_saved_unit_work import apply
                    if kind == ADJACENT_KIND:
                        from .xp2_lan_unit_work import archive_scope
                        with archive_scope(self.transport, p, before_observation, action):
                            effect = {'observation': apply(self, p, action, turn, before_observation, player_id=pid)}
                    else:
                        effect = {'observation': apply(self, p, action, turn, before_observation, player_id=pid)}
                elif is_purchase:
                    if b.load_abi.core_sha256 == XP1_CORE_SHA256:
                        if 'plot_id' in action:
                            from .xp1_plot_purchases import apply
                        else:
                            from .xp1_city_purchases import apply
                        effect = apply(session, action, before_observation)
                    else:
                        from .xp2_plot_purchases import apply
                        effect = dict(observation=apply(session, action, before_observation, allow_faith=True))
                elif is_government:
                    from .xp2_government import apply
                    effect=apply(session,action,before_observation)
                elif is_policy:
                    if action['kind'] == 'policy_unlock':
                        from .xp2_policy_unlock import apply
                    else:
                        from .xp2_policies import apply
                    effect = apply(session, action, before_observation)
                elif is_promotion:
                    if b.load_abi.core_sha256 == XP1_CORE_SHA256:
                        from .xp1_promotions import apply
                        effect = apply(session, action, before_observation)
                    else:
                        from .xp2_promotions import apply
                        effect = dict(observation=apply(session, action, before_observation))
                elif is_upgrade:
                    if b.load_abi.core_sha256 == XP1_CORE_SHA256:
                        from .xp1_unit_upgrades import apply
                        effect = apply(session,action,before_observation)
                    else:
                        from .xp2_unit_upgrades import apply
                        effect = dict(observation=apply(session, action, before_observation))
                elif is_religion_custom_names:
                    from .xp1_religion_custom_names import apply
                    effect=apply(session,action,before_observation)
                elif is_religion_founding:
                    from .xp1_religion_founding import apply
                    effect=apply(session,action,before_observation)
                elif is_great_people:
                    from .xp1_great_people_commands import apply
                    effect=apply(session,action,before_observation)
                elif is_great_work:
                    from .xp2_great_work_commands import apply
                    effect = apply(session, action, before_observation)
                elif is_artifact_origin:
                    from .xp2_archaeology import apply
                    effect = apply(session, action, before_observation)
                elif is_excavation:
                    from .xp2_archaeology_excavation import apply
                    effect = apply(session, action, before_observation)
                elif is_air:
                    from .xp2_air_operations import apply
                    effect = apply(session, action, before_observation)
                elif is_build_route:
                    from .xp2_build_route import apply
                    effect = apply(session, action, before_observation)
                elif is_park_designation:
                    from .xp2_designate_park import apply
                    effect = apply(session, action, before_observation)
                elif is_rock_concert:
                    from .xp2_rock_bands import apply
                    effect = apply(session, action, before_observation)
                elif is_great_person_activation:
                    from .xp1_great_person_activation import apply
                    effect=apply(session,action,before_observation)
                elif is_religious_unit_operation:
                    from .xp1_religious_unit_operations import apply
                    effect=apply(session,action,before_observation)
                elif is_prophet_activation:
                    from .xp1_prophet_activation import apply
                    effect=apply(session,action,before_observation)
                elif is_belief:
                    from .xp1_religion_beliefs import apply
                    effect=apply(session,action,before_observation)
                elif is_pantheon:
                    from .xp1_pantheon import apply
                    effect=apply(session,action,before_observation)
                elif is_order:
                    from .xp1_unit_orders import apply
                    effect=apply(session,action,before_observation)
                elif is_queue:
                    from .xp1_production_queue import apply
                    effect=apply(session,action,before_observation)
                elif is_placement:
                    from .xp1_production_placement import apply
                    effect=apply(session,action,before_observation)
                elif is_attack:
                    from .xp1_unit_attacks import apply
                    effect=apply(session,action,before_observation)
                elif is_occupation:
                    from .captured_city_session import apply
                    effect=apply(session,action,before_observation)
                elif is_city_shot:
                    district = kind == 'district_range_attack'
                    if b.load_abi.core_sha256 == XP2_CORE_SHA256:
                        from .native import native_saved_city_shot, native_saved_district_shot
                        shot = native_saved_district_shot if district else native_saved_city_shot
                        result = native_saved_city_shot.execute(session, p, action, turn, before_observation,
                            player_id=pid, expected_catalogue=self.explicit_ranged_shots[kind],
                            expected_defenses=self.explicit_city_shot_defenses,
                            validate=shot.validate_action, read_catalogue=shot.catalog,
                            compare=shot.compare_own_cities, offers=shot.actions,
                            request=shot.request_source, verify_effect=shot.effect,
                            shooter='district' if district else 'city', proof_sha=shot.PROOF_SHA)
                    elif b.load_abi.core_sha256 == XP1_CORE_SHA256:
                        from .xp1_city_shot import apply
                        result = apply(session, p, action, turn, before_observation)
                    else:
                        raise ValueError('Ranged shot requires a supported engine and shooter')
                    effect = dict(observation=result)
                elif is_city:
                    from .expansion_city_controls import apply
                    effect=apply(session,action,before_observation)
                elif is_governor:
                    from .xp2_governors import apply
                    effect=apply(session,action,before_observation)
                elif is_envoy:
                    from .xp2_envoys import apply
                    effect=apply(session,action,before_observation)
                elif is_levy:
                    from .xp1_city_state_levies import apply
                    effect=apply(session,action,before_observation)
                elif kind=='found_city':
                    effect=p.inspect_found_city(pid,unit_id=action['unit_id'],
                                                expected_x=action['x'],expected_y=action['y'])
                elif kind in ('research','civic'):
                    from .native import native_research_catalog as research
                    from .native import native_research_actions as research_effect
                    catalog=research.parse_catalog(self.runtime.evaluate_text(self.ui_child,
                        research.catalog_source(pid,kind,turn,core_sha256=b.load_abi.core_sha256),
                        b'@explicit_research_revalidation',capacity=131072),pid,kind,turn)
                    choice=research.choose(catalog,action['index'])
                    if choice['selected_hash']!=action['hash']:
                        raise RuntimeError('Research catalogue identity changed')
                    p.inspect_player_research_choice(pid,kind,selected_index=action['index'])
                    effect=research_effect.parse_effect(self.runtime.evaluate_text(self.ui_child,
                        research_effect.effect_source(pid,kind,action['index'],core_sha256=b.load_abi.core_sha256),
                        b'@explicit_research_effect',capacity=1024),pid,kind,action['index'],turn)
                    if effect['confirmed'] is not True:
                        raise RuntimeError('Native explicit research choice was not confirmed')
                else:
                    from .explicit_production_operation import apply
                    apply(self,p,action,turn,player_id=pid,core_sha256=b.load_abi.core_sha256)
                feedback_owner = getattr(self, 'trade_feedback', None)
                if feedback_owner is not None and feedback_owner.events:
                    feedback = self.flush_trade_feedback()
                    if feedback:
                        b.emit('xp2_bbg_trade_gameplay_delivered', feedback=feedback)
                action_done = perf_counter()
                self.transport.require_empty_native_queue()
                pending_statement=(is_war_response or is_initial_diplomacy) and effect.get('pending_statement_retained') is True
                control=b.control(empty=True,**({'allow_diplomacy':True} if pending_statement else {}))
                observed=observe_player(self.runtime,self.ui_child,before_observation['player_id'])
                if has_observation_effect and observed!=effect['observation']:
                    raise ValueError('Native action effect differs from the final player observation')
                if not (is_turn or congress_turn) and observed['turn']!=turn:
                    raise ValueError('Native explicit choice changed the turn unexpectedly')
                if (is_turn or congress_turn) and observed['turn'] not in (turn,turn+1):
                    raise ValueError('One native turn transition crossed an unqualified turn interval')
                if kind=='found_city' and (len(observed['cities'])!=len(before_observation['cities'])+1
                        or len(observed['units'])!=len(before_observation['units'])-1):
                    raise ValueError('Native foundation effect is inconsistent with the player observation')
                after=b.jobs_snapshot('after');require_quiescent(after)
                before_scope_exit = perf_counter()
            scope_exited = perf_counter()
            self.check(active=True)
            result=dict(action=deepcopy(action),effect=effect,observation_before=before_observation,
                observation_after=observed,jobs_before=before,jobs_after=after,control_after=control,
                episode_id=self.identity.episode_id,game_generation=self.identity.game_generation,
                sequence=self.sequence+1,publication_count=self.publication_count,
                unit_source=self.unit_source,
                public_runtime_admitted=False,complete_action_space=False,game_update_called=pump,
                same_save_official_transition_compared=False)
            if is_turn:
                b.emit('native_saved_turn_transition_timing', operation=kind,
                    continuation_sequence=self.sequence+1,
                    preflight_seconds=before_scope-started,
                    source_scope_seconds=(scope_entered-before_scope)+(scope_exited-before_scope_exit),
                    turn_route_seconds=action_done-scope_entered,
                    postflight_seconds=before_scope_exit-action_done,
                    finalization_seconds=perf_counter()-scope_exited)
            self.observation=observed;self.sequence+=1;b.stage=READY;b.busy=False
            return result
        except BaseException:
            self.poisoned=True;self.lease.poison();b.stage='poisoned';b.busy=False
            raise

    def check_close(self):
        self.check(active=False)
        if self.publishing:raise ValueError('Cannot close during native publication')
        self.transport.require_empty_native_queue();self.owner.control(empty=True)
