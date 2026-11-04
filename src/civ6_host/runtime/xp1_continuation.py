"""One retained XP1 continuation capability on the existing loaded owner.

Shared operation methods use the real UI child, command transport and publisher.
This candidate capability is not public session admission or a substitute loader.
"""
from copy import deepcopy
from civ6_host.contracts.unit_work import NETWORK_ACTION_FIELDS as UNIT_WORK_FIELDS
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256

READY='xp1-continuation-ready'
ACTIVE='xp1-continuation-active'

def validate_command(action):
    if type(action) is not dict:
        raise ValueError('Explicit command dictionary required')
    if action.get('kind') == 'purchase':
        from civ6_host.contracts.plot_purchases import validate_purchase_action
        validate_purchase_action(action)
        return
    if action.get('kind') == 'promote_unit':
        from civ6_host.contracts.unit_promotions import validate_action
        validate_action(action)
        return
    if action.get('kind') == 'upgrade_unit':
        from civ6_host.contracts.unit_upgrades import validate_action
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
    from .native.native_unit_actions import _identifier
    _identifier(action['unit_id'],'unit ID',0xFFFFFFFF)
    _identifier(action['x'],'founder x',65535);_identifier(action['y'],'founder y',65535)


def validate_unit_command(action):
    """Retained narrow diagnostic guard; shared session uses validate_command."""
    if type(action) is not dict or action.get('kind') != 'found_city':
        raise ValueError('Explicit foundation command required')
    validate_command(action)

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
        self._xp1_production_queue_catalogue=None
        self.explicit_placements={}
        self.explicit_combat_units=None
        self.explicit_combat_cities=None
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
        validate_command(action)
        xp2 = self.owner.load_abi.core_sha256 == XP2_CORE_SHA256
        if not xp2 and action['kind'] in UNIT_WORK_FIELDS:
            raise ValueError('Expansion unit work requires the verified XP2 route')
        if not xp2 and action['kind'] in ('purchase', 'promote_unit', 'upgrade_unit'):
            raise ValueError('Expansion command requires the verified XP2 route')
        if (xp2 and action['kind'] not in UNIT_WORK_FIELDS and action['kind'] not in
                ('found_city','research','civic','production','end_turn','force_end_turn','unready_turn',
                 'world_select_unit','world_deselect_unit','world_plot_click','unit_order',
                 'queue_append','queue_remove','queue_swap','production_placement','production_resume','unit_attack','city_range_attack','district_range_attack','city_focus','city_citizen','purchase','promote_unit','upgrade_unit')):
            raise ValueError('XP2 command family is not yet source-qualified in this session')
        return self._transition(action,session=session,pump=False)

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
        is_world=not pump and action['kind'] in WORLD_KINDS
        is_order=not pump and action['kind']=='unit_order'
        is_queue=not pump and action['kind'] in ('queue_append','queue_remove','queue_swap')
        is_placement=not pump and action['kind'] in ('production_placement','production_resume')
        is_attack=not pump and action['kind']=='unit_attack'
        is_city_shot=not pump and action['kind'] in ('city_range_attack', 'district_range_attack')
        is_city=not pump and action['kind'] in ('city_focus','city_citizen')
        is_work=not pump and action['kind'] in UNIT_WORK_FIELDS
        is_purchase=not pump and action['kind']=='purchase'
        is_promotion=not pump and action['kind']=='promote_unit'
        is_upgrade=not pump and action['kind']=='upgrade_unit'
        has_observation_effect = (is_world or is_order or is_queue or is_placement or is_attack
                                  or is_city or is_city_shot or is_work or is_purchase or is_promotion
                                  or is_upgrade)
        if is_turn or has_observation_effect:
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
                elif is_world:
                    from .xp1_world_input import apply
                    effect=apply(session,action,before_observation)
                elif is_work:
                    from .native.native_saved_unit_work import apply
                    effect = {'observation': apply(self, p, action, turn, before_observation, player_id=pid)}
                elif is_purchase:
                    from .xp2_plot_purchases import apply
                    effect = dict(observation=apply(session, action, before_observation))
                elif is_promotion:
                    from .xp2_promotions import apply
                    effect = dict(observation=apply(session, action, before_observation))
                elif is_upgrade:
                    from .xp2_unit_upgrades import apply
                    effect = dict(observation=apply(session, action, before_observation))
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
                elif is_city_shot:
                    from .native import native_saved_city_shot, native_saved_district_shot
                    district = kind == 'district_range_attack'
                    shot = native_saved_district_shot if district else native_saved_city_shot
                    if b.load_abi.core_sha256 != XP2_CORE_SHA256:
                        raise ValueError('City-shot action requires the XP2 session')
                    result = native_saved_city_shot.execute(session, p, action, turn, before_observation,
                        player_id=pid, expected_catalogue=self.explicit_ranged_shots[kind],
                        expected_defenses=self.explicit_city_shot_defenses,
                        validate=shot.validate_action, read_catalogue=shot.catalog,
                        compare=shot.compare_own_cities, offers=shot.actions,
                        request=shot.request_source, verify_effect=shot.effect,
                        shooter='district' if district else 'city', proof_sha=shot.PROOF_SHA)
                    effect = dict(observation=result)
                elif is_city:
                    from .expansion_city_controls import apply
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
                action_done = perf_counter()
                self.transport.require_empty_native_queue();control=b.control(empty=True)
                observed=observe_player(self.runtime,self.ui_child,before_observation['player_id'])
                if has_observation_effect and observed!=effect['observation']:
                    raise ValueError('Native action effect differs from the final player observation')
                if not is_turn and observed['turn']!=turn:
                    raise ValueError('Native explicit choice changed the turn unexpectedly')
                if is_turn and observed['turn'] not in (turn,turn+1):
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
