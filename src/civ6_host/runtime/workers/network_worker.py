"""Persistent LAN worker over the shared official loader and action adapters."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
from civ6_host.runtime.import_boundary import enable as _enable
_enable()

import json
import os
import sys
from time import perf_counter
from contextlib import nullcontext


def _save_before_close(owner, protocol, closure, path, request, expansion, emit):
    outcome = protocol.last_outcome
    pid = request['player_id']
    native = outcome.get('native_victory')
    if (not outcome['terminated'] and expansion and closure.get('secondary_unit_commands') is True
            and type(native) is dict and native.get('player_id') != pid):
        # The close owner stays local even if the last response belonged to a peer.
        native = _read_xp1_outcome(owner, pid)
        outcome = dict(terminated=native['episode_terminated'], native_victory=native)
    if outcome['terminated']:
        # The checkpoint writer requires a live decision boundary.
        emit('native_checkpoint_skipped', reason='official_native_victory',
             sequence=request['sequence'])
        return
    if type(native) is dict and native.get('player_id') == pid and native.get('is_alive') is False:
        from civ6_host.contracts.session_result import project_inactive_player
        inactive = project_inactive_player(outcome, episode_id=protocol.identity.episode_id,
            game_generation=protocol.identity.game_generation, player_id=pid, turn=protocol.session['turn'])
        if inactive is not None:
            emit('native_checkpoint_skipped', reason='acting_player_eliminated',
                 player_id=pid, turn=inactive['turn'], sequence=request['sequence'])
            return
    if expansion:
        from civ6_host.runtime import xp1_session_checkpoint, xp1_session_view
        _, observation, decisions = xp1_session_view.read(owner, pid, protocol.sequence)
        xp1_session_checkpoint.save(owner, observation, decisions, closure, path, request['sequence'])
    else:
        from civ6_host.runtime import network_checkpoint, network_owner
        observation, decisions = network_owner.read(owner, protocol.sequence, protocol.rounds,
            round_limit=protocol.limit, player_id=pid)
        network_checkpoint.save(owner, observation, decisions, closure, path)


def _open_xp1(closure, path, emit, win):
    """Use the retained saved-Load graph, not another worker or scheduler."""
    started = perf_counter()
    from civ6_host.runtime.xp1_session_inputs import (
        SAVED_LOAD_CLOSURE_ENV, digest, saved_load_build_pins, _write_once)
    from civ6_host.runtime.provenance import verify_installation
    from civ6_host.runtime.captured_saved_load import select_load_closure
    selected=select_load_closure(closure)
    from civ6_host.runtime.xp2_world_war import source_pin
    war_source_sha256 = source_pin(closure.get('war_source_sha256'), selected.family)
    governors_diagnostic = closure.get('governors_diagnostic', False)
    initial_diplomacy = closure.get('diplomacy_overview_diagnostic', False)
    trade_diagnostic = closure.get('trade_diagnostic', False)
    standard_trade = closure.get('standard_trade', False)
    xp1_trade = closure.get('xp1_trade', False)
    xp1_trade_overview = closure.get('xp1_trade_overview', False)
    xp1_government = closure.get('xp1_government', False)
    xp1_plot_purchase = closure.get('xp1_plot_purchase', False)
    xp1_city_purchase = closure.get('xp1_city_purchase', False)
    xp1_faith_purchase = closure.get('xp1_faith_purchase', False)
    xp1_city_buildings = closure.get('xp1_city_buildings', False)
    xp1_unit_work = closure.get('xp1_unit_work', False)
    score_requested = closure.get('world_score', False)
    archaeology_requested = closure.get('xp2_archaeology', False)
    archaeology_commands = closure.get('xp2_archaeology_commands', False)
    air_requested = closure.get('xp2_air_operations', False)
    route_requested = closure.get('xp2_build_route', False)
    designate_park_requested = closure.get('xp2_designate_park', False)
    rock_bands_requested = closure.get('xp2_rock_bands', False)
    extra_unit_orders_requested = closure.get('xp2_extra_unit_orders', False)
    growth_requested = closure.get('expansion_city_growth', False)
    loyalty_requested = closure.get('expansion_city_loyalty', False)
    parks_requested = closure.get('expansion_national_parks', False)
    xp1_promotions = closure.get('xp1_promotions', False)
    xp1_unit_upgrades = closure.get('xp1_unit_upgrades', False)
    xp1_pantheon = closure.get('xp1_pantheon', False)
    xp1_religion_beliefs = closure.get('xp1_religion_beliefs', False)
    xp1_religion_founding = closure.get('xp1_religion_founding', False)
    xp1_religion_custom_names = closure.get('xp1_religion_custom_names', False)
    xp1_prophet_activation = closure.get('xp1_prophet_activation', False)
    xp1_great_person_activation = closure.get('xp1_great_person_activation', False)
    xp1_religious_unit_operations = closure.get('xp1_religious_unit_operations', False)
    xp2_religious_unit_operations = closure.get('xp2_religious_unit_operations', False)
    xp2_prophet_activation = closure.get('xp2_prophet_activation', False)
    xp2_religion_founding = closure.get('xp2_religion_founding', False)
    xp2_religion_beliefs = closure.get('xp2_religion_beliefs', False)
    xp2_pantheon = closure.get('xp2_pantheon', False)
    xp2_city_religion_details = closure.get('xp2_city_religion_details', False)
    xp2_great_people = closure.get('xp2_great_people', False)
    xp2_great_people_actions = closure.get('xp2_great_people_actions', False)
    xp2_great_person_activation = closure.get('xp2_great_person_activation', False)
    xp2_city_buildings = closure.get('xp2_city_buildings', False)
    xp1_city_religion_details = closure.get('xp1_city_religion_details', False)
    xp1_great_people = closure.get('xp1_great_people', False)
    xp1_great_people_actions = closure.get('xp1_great_people_actions', False)
    xp1_great_people_reject = closure.get('xp1_great_people_reject', False)
    unit_formations = closure.get('unit_formations', False)
    stock_dedications = closure.get('stock_dedications', False)
    city_state_levies = closure.get('city_state_levies', False)
    espionage_diagnostic = closure.get('espionage_diagnostic', False)
    world_congress_diagnostic = closure.get('world_congress_diagnostic', False)
    world_congress_review_diagnostic = closure.get('world_congress_review_diagnostic', False)
    trade_overview_ui_selected = closure.get('trade_overview_ui_selected', False)
    if (type(initial_diplomacy) is not bool or initial_diplomacy and (
            selected.family != 'xp2-lan' or not (governors_diagnostic is True or standard_trade is True)
            or war_source_sha256 is None or 'execution_image' not in closure)):
        raise ValueError('Initial diplomacy requires an exact current XP2 closure')
    if initial_diplomacy and standard_trade is True:
        from civ6_host.runtime.xp2_diplomacy_overview import require_stock_capture
        require_stock_capture(selected.reference)
    if type(trade_diagnostic) is not bool or trade_diagnostic and not initial_diplomacy:
        raise ValueError('Trade requires the complete current XP2 v33 closure')
    if (type(standard_trade) is not bool or standard_trade and (
            selected.family != 'xp2-lan' or trade_diagnostic or governors_diagnostic
            or 'execution_image' not in closure)):
        raise ValueError('Standard trade requires the exact stock XP2 closure')
    if type(unit_formations) is not bool or unit_formations and not standard_trade:
        raise ValueError('Unit formations require the exact stock XP2 closure')
    if type(stock_dedications) is not bool or stock_dedications and not unit_formations:
        raise ValueError('Dedications require the exact stock XP2 v2 closure')
    if type(espionage_diagnostic) is not bool or espionage_diagnostic and not trade_diagnostic:
        raise ValueError('Espionage requires the complete current XP2 trade closure')
    if (type(world_congress_diagnostic) is not bool or world_congress_diagnostic and not (
            espionage_diagnostic or stock_dedications and world_congress_review_diagnostic is True)):
        raise ValueError('World Congress requires the complete XP2 BBG or stock review closure')
    if (type(world_congress_review_diagnostic) is not bool
            or world_congress_review_diagnostic and world_congress_diagnostic is not True):
        raise ValueError('Congress review requires its exact Boolean Congress closure')
    if type(governors_diagnostic) is not bool:
        raise ValueError('Exact governors diagnostic option required')
    if governors_diagnostic:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if selected.family != 'xp2-lan' or selected.core_sha256 != XP2_CORE_SHA256:
            raise ValueError('Governors diagnostic requires the XP2 LAN core')
    raw = _Path(path).read_bytes()
    if digest(raw) != os.environ.get(SAVED_LOAD_CLOSURE_ENV):
        raise ValueError('XP1 private session closure changed')
    from civ6_host.runtime.capture_admission import XP2_LAUNCH_FIELD
    if selected.family == 'xp2-lan' and XP2_LAUNCH_FIELD not in closure:
        raise ValueError('XP2 worker requires its prepared launch binding')
    from civ6_host.runtime.session_limits import standard_lifetime_limit
    if (type(closure.get('lifetime_seconds')) is not int
            or not 1 <= closure['lifetime_seconds'] <= standard_lifetime_limit(closure.get('input_profile'))
            or closure.get('resume_checkpoint') is not None
            or 'unit_command' in closure
            or any(closure.get(name) is not True for name in (
                'raw_only_candidate', 'post160_candidate', 'publish_cache_candidate',
                'close_loaded_candidate', 'observe_player_candidate', 'unit_commands_candidate'))
            or any(closure.get(name, False) is not False for name in (
                'forced_endturn_diagnostic', 'production_queue_diagnostic',
                'multiturn_movement_diagnostic', 'movement_information_diagnostic',
                'unit_order_cancel_diagnostic', 'world_input_diagnostic'))):
        raise ValueError('XP1 network session has an unsupported capability request')
    from civ6_host.runtime.expansion_city_controls import requested
    city_flags=requested(closure)
    verify_installation()
    execution_options = {}
    if 'execution_image' in closure:
        from civ6_host.runtime.execution_images import from_identity
        execution_options['execution_image'] = from_identity(closure['execution_image'])
    if city_flags[0]:
        from civ6_host.runtime.expansion_city_controls_profile import source_dependencies
        for source, expected in source_dependencies(selected.core_sha256,
                official_bundle=selected.reference, **execution_options).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('City-control source is outside the worker closure')
    if type(city_state_levies) is not bool:
        raise ValueError('Military levy capability must be an exact Boolean')
    if city_state_levies:
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.xp2_city_state_levies import source_dependencies
        if selected.family != 'xp2-lan' or execution_options.get('execution_image') is not _PROFILE:
            raise ValueError('Military levies require the installed Gathering Storm LAN closure')
        for source, expected in source_dependencies(_PROFILE).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Military levy source is outside the worker closure')
    if trade_diagnostic:
        from civ6_host.runtime import xp2_bbg_trade_feedback, xp2_trade
        from civ6_host.runtime.resource_resolution import resolve_path
        from civ6_host.runtime.captured_session_profile import require_bbg_capture
        require_bbg_capture(selected.reference, **execution_options)
        for module in (xp2_trade, xp2_bbg_trade_feedback):
            for source, expected in module.source_dependencies(**execution_options).items():
                if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                    raise ValueError('Trade source is outside the worker closure')
    if standard_trade:
        from civ6_host.runtime import xp2_trade
        from civ6_host.runtime.resource_resolution import resolve_path
        dependencies = xp2_trade.standard_source_dependencies(selected.reference,
            core_sha256=selected.core_sha256, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Standard trade source is outside the worker closure')
    if unit_formations:
        from civ6_host.runtime import xp2_unit_formations
        dependencies = xp2_unit_formations.source_dependencies(selected.reference, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Unit formation source is outside the worker closure')
    if stock_dedications:
        from civ6_host.runtime import xp2_dedications
        dependencies = xp2_dedications.source_dependencies(selected.reference, **execution_options)
        for source, expected in dependencies.items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Dedication source is outside the worker closure')
    if espionage_diagnostic:
        from civ6_host.runtime import xp2_espionage
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in xp2_espionage.source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Espionage source is outside the worker closure')
    if world_congress_diagnostic:
        from civ6_host.runtime.xp2_world_congress_source import source_dependencies
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Congress source is outside the worker closure')
    if world_congress_review_diagnostic:
        from civ6_host.runtime.xp2_world_congress_review import source_dependencies
        from civ6_host.runtime.resource_resolution import resolve_path
        for source, expected in source_dependencies(**execution_options).items():
            if closure['pins'].get(str(resolve_path(_Path(source)).resolve())) != expected:
                raise ValueError('Congress review source is outside the worker closure')
    if type(trade_overview_ui_selected) is not bool or trade_overview_ui_selected and not world_congress_review_diagnostic:
        raise ValueError('Trade overview requires the exact complete XP2 public decision closure')
    if trade_overview_ui_selected:
        from civ6_host.runtime import xp2_trade_overview
        for source, expected in xp2_trade_overview.source_dependencies(
                selected.reference, execution_options.get('execution_image')).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Trade overview source is outside the worker closure')
    from civ6_host.runtime import (xp1_captured_city, xp1_city_shot, xp1_dedications_source,
                                  xp1_governors_source, xp2_captured_city)
    occupation_image = execution_options.get('execution_image')
    if score_requested:
        from civ6_host.runtime import world_score
        for source, expected in world_score.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('World score UI source is outside the worker closure')
    if route_requested:
        from civ6_host.runtime import xp2_build_route

        for source, expected in xp2_build_route.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Build Route source is outside the worker closure')
    if designate_park_requested:
        from civ6_host.runtime import xp2_designate_park

        for source, expected in xp2_designate_park.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Park designation source is outside the worker closure')
    if extra_unit_orders_requested:
        from civ6_host.runtime import xp2_extra_unit_orders

        for source, expected in xp2_extra_unit_orders.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Additional unit-order source is outside the worker closure')
    if rock_bands_requested:
        from civ6_host.runtime import xp2_rock_bands

        for source, expected in xp2_rock_bands.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rock-band source is outside the worker closure')
    if air_requested:
        from civ6_host.runtime import xp2_air_operations

        for source, expected in xp2_air_operations.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Air operation source is outside the worker closure')
    if archaeology_requested:
        from civ6_host.runtime import xp2_archaeology

        for source, expected in xp2_archaeology.source_dependencies(
                selected.reference, occupation_image, commands=archaeology_commands).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Archaeology source is outside the worker closure')
    if growth_requested:
        from civ6_host.runtime import expansion_city_growth
        for source, expected in expansion_city_growth.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('City growth UI source is outside the worker closure')
    if loyalty_requested:
        from civ6_host.runtime import expansion_city_loyalty
        for source, expected in expansion_city_loyalty.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('City loyalty UI source is outside the worker closure')
    if parks_requested:
        from civ6_host.runtime import expansion_national_parks
        for source, expected in expansion_national_parks.source_dependencies(selected.reference, occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('National park UI source is outside the worker closure')
    xp1_occupation = xp1_captured_city.supports(selected.reference, occupation_image)
    xp1_dedications = xp1_dedications_source.supports(selected.reference, occupation_image)
    if xp1_trade:
        from civ6_host.runtime import xp1_trade_source
        if (not xp1_occupation or not xp1_dedications
                or not xp1_trade_source.supports(selected.reference, occupation_image)):
            raise ValueError('Rise and Fall trade requires its exact saved-load route')
        for source, expected in xp1_trade_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall trade source is outside the worker closure')
    if xp1_trade_overview:
        from civ6_host.runtime.xp2_trade_overview import stock_source_dependencies
        if not xp1_trade:
            raise ValueError('Rise and Fall trade overview requires its exact trade session')
        for source, expected in stock_source_dependencies(selected.reference,
                core_sha256=selected.core_sha256, execution_image=occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall trade overview source is outside the worker closure')
    if xp1_government:
        from civ6_host.runtime import xp1_government_policy_source
        if (not xp1_dedications
                or not xp1_government_policy_source.supports(selected.reference, occupation_image)):
            raise ValueError('Rise and Fall government requires its exact stock capture and engine')
        for source, expected in xp1_government_policy_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall government source is outside the worker closure')
    if xp1_plot_purchase:
        from civ6_host.runtime import xp1_plot_purchases
        if not xp1_dedications or not xp1_plot_purchases.supports(selected.reference, occupation_image):
            raise ValueError('Rise and Fall plot purchase requires its exact stock capture and engine')
        for source, expected in xp1_plot_purchases.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall plot purchase source is outside the worker closure')
    if xp1_faith_purchase and not xp1_city_purchase:
        raise ValueError('Rise and Fall faith purchases require the stock city purchase catalogue')
    if xp1_city_purchase:
        from civ6_host.runtime.xp1_city_purchases import source_dependencies
        if not xp1_plot_purchase:
            raise ValueError('Rise and Fall city purchases require the stock gold purchase catalogue')
        for source, expected in source_dependencies(occupation_image, allow_faith=xp1_faith_purchase).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall city purchase source is outside the worker closure')
    if xp1_city_buildings:
        from civ6_host.runtime import xp1_city_buildings as building_inventory
        if not xp1_dedications or not building_inventory.supports(selected.reference,occupation_image):
            raise ValueError('Rise and Fall city buildings require their exact stock capture and engine')
        for source,expected in building_inventory.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall building inventory source is outside the worker closure')
    if xp1_unit_work:
        from civ6_host.runtime import xp1_unit_work_profile
        if not xp1_unit_work_profile.supports(selected.reference, occupation_image):
            raise ValueError('Rise and Fall unit work requires its exact stock capture and engine')
        for source, expected in xp1_unit_work_profile.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall UnitPanel source is outside the worker closure')
    if xp1_promotions:
        from civ6_host.runtime import xp1_promotions as promotion_source
        if not xp1_dedications or not promotion_source.supports(selected.reference,occupation_image):
            raise ValueError('Rise and Fall promotions require their exact stock capture and engine')
        for source,expected in promotion_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall promotion source is outside the worker closure')
    if xp1_unit_upgrades:
        from civ6_host.runtime import xp1_unit_upgrades as upgrade_source
        if not xp1_dedications or not upgrade_source.supports(selected.reference,occupation_image):
            raise ValueError('Rise and Fall upgrades require their exact stock capture and engine')
        for source,expected in upgrade_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Rise and Fall upgrade source is outside the worker closure')
    if xp1_pantheon:
        from civ6_host.runtime import xp1_pantheon_source
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        if (not xp1_dedications or selected.reference != xp1_pantheon_source.REFERENCE
                or occupation_image is not _XP1_PROFILE):
            raise ValueError('Pantheon requires its exact installed Rise and Fall owner')
        xp1_pantheon_source.require_actions()
        for source,expected in xp1_pantheon_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Pantheon source is outside the worker closure')
    if xp1_religion_beliefs:
        from civ6_host.runtime import xp1_religion_beliefs_source
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        if not xp1_dedications or selected.reference != REFERENCE or occupation_image is not _XP1_PROFILE:
            raise ValueError('Belief choices require the exact installed Rise and Fall capture')
        xp1_religion_beliefs_source.require_actions()
        for source,expected in xp1_religion_beliefs_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Belief source is outside the worker closure')
    if xp1_religion_founding:
        from civ6_host.runtime import xp1_religion_founding_source
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        if not xp1_dedications or selected.reference != REFERENCE or occupation_image is not _XP1_PROFILE:
            raise ValueError('Religion founding requires the exact installed Rise and Fall capture')
        xp1_religion_founding_source.require_actions()
        for source,expected in xp1_religion_founding_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Religion founding source is outside the worker closure')
    if xp1_religion_custom_names:
        from civ6_host.runtime import xp1_religion_custom_names as names
        if (xp1_religion_founding is not True or not xp1_dedications
                or not names.supports(selected.reference, occupation_image)):
            raise ValueError('Custom religion naming requires the exact installed Rise and Fall foundation group')
        names.require_actions()
        for source,expected in names.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Custom religion naming source is outside the worker closure')
    if xp1_prophet_activation:
        from civ6_host.runtime import xp1_prophet_activation_source
        from civ6_host.runtime.xp1_saved_load import REFERENCE
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        if not xp1_dedications or selected.reference != REFERENCE or occupation_image is not _XP1_PROFILE:
            raise ValueError('Prophet activation requires the exact installed Rise and Fall capture')
        xp1_prophet_activation_source.require_actions()
        for source,expected in xp1_prophet_activation_source.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Prophet activation source is outside the worker closure')
    if xp1_great_person_activation:
        from civ6_host.runtime import xp1_great_person_activation_source as activation
        if not xp1_dedications or not activation.supports(selected.reference,occupation_image):
            raise ValueError('Great Person activation requires the exact installed Rise and Fall capture')
        activation.require_actions()
        for source,expected in activation.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Great Person activation source is outside the worker closure')
    if xp1_great_people:
        from civ6_host.runtime import xp1_great_people as people
        if not xp1_dedications or not people.supports(selected.reference, occupation_image):
            raise ValueError('Great People require the exact installed Rise and Fall owner')
        for source,expected in people.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Great People source is outside the worker closure')
    if type(xp1_city_religion_details) is not bool:
        raise ValueError('Exact Rise and Fall city religion detail Boolean required')
    if xp1_city_religion_details:
        from civ6_host.runtime import xp1_city_religion
        if (selected.family != 'xp1-lan' or selected.reference != xp1_city_religion.REFERENCE
                or occupation_image is not xp1_city_religion._XP1_PROFILE):
            raise ValueError('City religion details require the exact installed Rise and Fall capture')
        for source,expected in xp1_city_religion.source_dependencies(occupation_image,include_details=True).items():
            if closure['pins'].get(source) != expected:
                raise ValueError('City religion detail source is outside the worker closure')
    if xp1_religious_unit_operations:
        from civ6_host.runtime import xp1_religious_unit_operations as religious
        if not xp1_dedications or not religious.supports(selected.reference,occupation_image):
            raise ValueError('Religious unit operations require the exact installed Rise and Fall capture')
        religious.require_actions()
        for source,expected in religious.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Religious unit operation source is outside the worker closure')
    if type(xp2_religious_unit_operations) is not bool:
        raise ValueError('Exact Gathering Storm religious unit operation Boolean required')
    if type(xp2_city_religion_details) is not bool:
        raise ValueError('Exact Gathering Storm city religion detail Boolean required')
    if xp2_city_religion_details:
        from civ6_host.runtime import xp1_city_religion
        if selected.family != 'xp2-lan' or not xp1_city_religion.supports(selected.reference,occupation_image):
            raise ValueError('City religion details require the exact admitted Gathering Storm capture and image')
        for dependency_path,expected in xp1_city_religion.source_dependencies(occupation_image,
                include_details=True,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('City religion detail source is outside the Gathering Storm worker closure')
    if type(xp2_city_buildings) is not bool:
        raise ValueError('Exact Gathering Storm city buildings Boolean required')
    if xp2_city_buildings:
        from civ6_host.runtime import xp2_city_buildings as buildings
        if (selected.family != 'xp2-lan' or not (standard_trade or trade_diagnostic)
                or not buildings.supports(selected.reference, occupation_image)):
            raise ValueError('Gathering Storm buildings require an admitted capture and image')
        dependencies = buildings.source_dependencies(occupation_image, reference=selected.reference)
        for dependency_path, expected in dependencies.items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('City building source is outside the Gathering Storm worker closure')
    if xp2_great_people:
        from civ6_host.runtime.xp2_great_people_source import source_dependencies
        dependencies = source_dependencies(occupation_image, reference=selected.reference,
                                           include_actions=xp2_great_people_actions)
        for dependency_path, expected in dependencies.items():
            if closure['pins'].get(dependency_path) != expected:
                raise ValueError('Great People source is outside the Gathering Storm worker closure')
    if xp2_great_person_activation:
        from civ6_host.runtime import xp2_great_person_activation_source as activation
        dependencies = activation.source_dependencies(occupation_image, reference=selected.reference)
        for dependency_path, expected in dependencies.items():
            if closure['pins'].get(dependency_path) != expected:
                raise ValueError('Great Person activation source is outside the Gathering Storm worker closure')
    if xp2_religious_unit_operations:
        from civ6_host.runtime import xp1_religious_unit_operations as religious
        if selected.family != 'xp2-lan' or not religious.supports(selected.reference,occupation_image):
            raise ValueError('Religious unit operations require the exact admitted Gathering Storm capture and image')
        religious.require_actions(occupation_image)
        for source,expected in religious.source_dependencies(occupation_image,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Gathering Storm religious unit operation source is outside the worker closure')
    if type(xp2_prophet_activation) is not bool:
        raise ValueError('Exact Gathering Storm prophet activation Boolean required')
    if xp2_prophet_activation:
        from civ6_host.runtime import xp1_prophet_activation_source as source
        if selected.family != 'xp2-lan' or not source.supports(selected.reference,occupation_image):
            raise ValueError('Prophet activation requires the exact admitted Gathering Storm capture and image')
        source.require_actions(occupation_image)
        for dependency_path,expected in source.source_dependencies(occupation_image,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('Gathering Storm prophet activation source is outside the worker closure')
    if type(xp2_religion_founding) is not bool:
        raise ValueError('Exact Gathering Storm religion founding Boolean required')
    if xp2_religion_founding:
        from civ6_host.runtime import xp1_religion_founding_source as source
        if selected.family != 'xp2-lan' or not source.supports(selected.reference,occupation_image):
            raise ValueError('Religion founding requires the exact admitted Gathering Storm capture and image')
        source.require_actions(occupation_image)
        for dependency_path,expected in source.source_dependencies(occupation_image,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('Gathering Storm religion founding source is outside the worker closure')
    if type(xp2_religion_beliefs) is not bool:
        raise ValueError('Exact Gathering Storm belief choices Boolean required')
    if xp2_religion_beliefs:
        from civ6_host.runtime import xp1_religion_beliefs_source as source
        if selected.family != 'xp2-lan' or not source.supports(selected.reference,occupation_image):
            raise ValueError('Belief choices requires the exact admitted Gathering Storm capture and image')
        source.require_actions(occupation_image)
        for dependency_path,expected in source.source_dependencies(occupation_image,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('Gathering Storm belief choices source is outside the worker closure')
    if type(xp2_pantheon) is not bool:
        raise ValueError('Exact Gathering Storm pantheon Boolean required')
    if xp2_pantheon:
        from civ6_host.runtime import xp1_pantheon_source as source
        if selected.family != 'xp2-lan' or not source.supports(selected.reference,occupation_image):
            raise ValueError('Pantheon requires the exact admitted Gathering Storm capture and image')
        source.require_actions(occupation_image)
        for dependency_path,expected in source.source_dependencies(occupation_image,reference=selected.reference).items():
            if closure['pins'].get(str(_Path(dependency_path).resolve())) != expected:
                raise ValueError('Gathering Storm pantheon source is outside the worker closure')
    if xp1_great_people_actions:
        from civ6_host.runtime import xp1_great_people_commands as commands
        if not xp1_dedications or xp1_great_people is not True or not commands.supports(
                selected.reference, occupation_image):
            raise ValueError('Great Person commands require the exact installed Rise and Fall query group')
        commands.require_actions()
        for source,expected in commands.source_dependencies(occupation_image).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Great Person command source is outside the worker closure')
    if xp1_great_people_reject:
        from civ6_host.runtime import xp1_great_people_commands as commands
        if (xp1_great_people_actions is not True or xp1_great_people is not True
                or not xp1_dedications or not commands.supports(selected.reference, occupation_image)):
            raise ValueError('Great Person rejection requires the exact installed command and query groups')
        commands.verify_reject_source()
        for source,expected in commands.source_dependencies(occupation_image,include_reject=True).items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Great Person rejection source is outside the worker closure')
    stock_captured_city = standard_trade and xp2_captured_city.supports_stock(
        selected.reference, occupation_image)
    xp2_occupation = stock_captured_city or (trade_diagnostic and trade_overview_ui_selected)
    if xp1_occupation or xp2_occupation:
        dependencies = ({**xp1_captured_city.source_dependencies(occupation_image),
                         **xp1_city_shot.source_dependencies(occupation_image),
                         **xp1_governors_source.source_dependencies(occupation_image),
                         **xp1_dedications_source.source_dependencies(occupation_image)} if xp1_occupation
                        else xp2_captured_city.source_dependencies(**execution_options, stock=stock_captured_city))
        for source, expected in dependencies.items():
            if closure['pins'].get(str(_Path(source).resolve())) != expected:
                raise ValueError('Captured-city source is outside the worker closure')
    if _Path(sys.executable).resolve() != saved_load_build_pins({}, ui=True,
            core_sha256=selected.core_sha256, official_bundle=selected.reference, **execution_options):
        raise ValueError('XP1 session requires its exact native UI executable')
    from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
    from civ6_host.runtime.xp1_session_admission import bind
    emit('native_reset_timing', phase='saved_worker_admission_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    started = perf_counter()
    saved = SavedLoadOwner.open(closure, emit, win)
    saved.xp1_governors_enabled = xp1_governors_source.supports(selected.reference, occupation_image)
    saved.xp1_dedications_enabled = xp1_dedications
    saved.governors_diagnostic = governors_diagnostic
    saved.diplomacy_overview_diagnostic = initial_diplomacy
    saved.trade_diagnostic = trade_diagnostic
    saved.standard_trade = standard_trade
    saved.xp1_trade = xp1_trade
    saved.xp1_trade_overview = xp1_trade_overview
    saved.xp1_government = xp1_government
    saved.xp1_plot_purchase = xp1_plot_purchase
    saved.xp1_city_purchase = xp1_city_purchase
    saved.xp1_faith_purchase = xp1_faith_purchase
    saved.xp1_city_buildings = xp1_city_buildings
    saved.xp1_promotions = xp1_promotions
    saved.xp1_unit_upgrades = xp1_unit_upgrades
    saved.xp1_pantheon = xp1_pantheon
    saved.xp1_religion_beliefs = xp1_religion_beliefs
    saved.xp1_religion_founding = xp1_religion_founding
    saved.xp1_religion_custom_names = xp1_religion_custom_names
    saved.xp1_prophet_activation = xp1_prophet_activation
    saved.xp1_great_person_activation = xp1_great_person_activation
    saved.xp1_religious_unit_operations = xp1_religious_unit_operations
    saved.xp2_religious_unit_operations = xp2_religious_unit_operations
    saved.xp2_prophet_activation = xp2_prophet_activation
    saved.xp2_religion_founding = xp2_religion_founding
    saved.xp2_religion_beliefs = xp2_religion_beliefs
    saved.xp2_pantheon = xp2_pantheon
    saved.xp2_city_religion_details = xp2_city_religion_details
    saved.xp2_great_people = xp2_great_people
    saved.xp2_great_people_actions = xp2_great_people_actions
    saved.xp2_great_person_activation = xp2_great_person_activation
    saved.xp2_city_buildings = xp2_city_buildings
    saved.xp1_city_religion_details = xp1_city_religion_details
    saved.xp1_great_people = xp1_great_people
    saved.xp1_great_people_actions = xp1_great_people_actions
    saved.xp1_great_people_reject = xp1_great_people_reject
    saved.unit_formations = unit_formations
    saved.stock_dedications = stock_dedications
    saved.xp2_city_state_levies_enabled = city_state_levies
    saved.espionage_diagnostic = espionage_diagnostic
    saved.world_congress_diagnostic = world_congress_diagnostic
    saved.world_congress_review_diagnostic = world_congress_review_diagnostic
    saved.trade_overview_ui_selected = trade_overview_ui_selected
    saved.war_source_sha256 = war_source_sha256
    run = _Path(path).resolve().parent
    emit('xp1_saved_raw_load_observed', receipt=_write_once(run/'raw-load-result.json', saved.raw_result))
    emit('native_reset_timing', phase='saved_raw_load_inclusive_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='inclusive; contains native Load phases')
    for method, filename, stage in (
            ('populate_caches', 'cache-result.json', 'xp1_saved_cache_observed'),
            ('postload', 'post160-result.json', 'xp1_saved_post160_sequence_returned'),
            ('publish', 'publication-result.json', 'xp1_saved_cache_publication_returned'),
            ('observe_initial', 'player-view-result.json', 'xp1_saved_player_view_returned')):
        before_stage = {'postload':'before_xp1_saved_post160_sequence',
                        'publish':'before_xp1_saved_cache_publication',
                        'observe_initial':'before_xp1_saved_player_view'}.get(method)
        if before_stage:
            emit(before_stage, public_runtime_admitted=False)
        started = perf_counter()
        result = getattr(saved, method)()
        emit(stage, receipt=_write_once(run/filename, result))
        emit('native_reset_timing', phase='saved_' + method + '_seconds',
             elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    started = perf_counter()
    saved.begin_commands()
    if xp1_unit_work:
        xp1_unit_work_profile.bind(saved)
    if score_requested:
        world_score.bind(saved)
    if archaeology_requested:
        xp2_archaeology.bind(saved, commands=archaeology_commands)
    if air_requested:
        xp2_air_operations.bind(saved)
    if route_requested:
        xp2_build_route.bind(saved)
    if designate_park_requested:
        xp2_designate_park.bind(saved)
    if rock_bands_requested:
        xp2_rock_bands.bind(saved)
    if extra_unit_orders_requested:
        xp2_extra_unit_orders.bind(saved)
    if growth_requested:
        expansion_city_growth.bind(saved)
    if loyalty_requested:
        expansion_city_loyalty.bind(saved)
    if parks_requested:
        expansion_national_parks.bind(saved)
    from civ6_host.runtime.expansion_city_controls import enable
    if city_flags[0]:enable(saved,closure)
    bind(saved)
    if trade_diagnostic:
        xp2_bbg_trade_feedback.bind(saved)
    if xp1_occupation:
        xp1_captured_city.bind(saved)
        xp1_city_shot.bind(saved)
    elif xp2_occupation:
        xp2_captured_city.bind(saved)
    if trade_overview_ui_selected or standard_trade or xp1_trade_overview:
        from civ6_host.runtime.xp2_trade_overview import bind_civic_hook
        bind_civic_hook(saved)
    saved._xp2_lan_world_input_enabled = closure.get('secondary_unit_commands', False)
    saved._xp2_lan_unit_development_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_unit_attacks_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_occupation_enabled = saved._xp2_lan_world_input_enabled and xp2_occupation
    saved._xp2_lan_ranged_shots_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_purchases_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_government_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_city_states_enabled = saved._xp2_lan_world_input_enabled
    saved._xp2_lan_unit_work_enabled = saved._xp2_lan_world_input_enabled
    if selected.family == 'xp2-lan':
        from civ6_host.runtime.xp2_lan_unit_work import bind_adjacent
        bind_adjacent(saved)
    compare_initial = None
    if saved.inputs.checkpoint is not None:
        from civ6_host.runtime.network_checkpoint import prepare_owner
        compare_initial = prepare_owner(saved, saved.continuation.observation)
    emit('native_reset_timing', phase='saved_command_and_checkpoint_binding_seconds',
         elapsed_seconds=perf_counter() - started, timing_scope='non-overlapping stage')
    return saved, compare_initial


def _emit_native_load_profile(owner, protocol, player_id, emit):
    """Emit a captured Load profile only after the actual episode exists."""
    captured = getattr(owner.backend, '_command_load_profile', None)
    if captured is None:
        return False
    failed = False
    try:
        expected = protocol.identity
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        if (owner.continuation is None
                or type(owner.continuation) is not SavedContinuation
                or owner.continuation.identity is not expected
                or type(captured) is not dict
                or set(captured) != {'profiler', 'wall_seconds', 'callback_failed', 'core_identity'}
                or captured['callback_failed'] is not False):
            raise RuntimeError('Captured native Load profile is not bound to a successful episode')
        from civ6_host.runtime.command_profiling import CommandProfiler
        profiler = CommandProfiler(enabled=True, emit=emit, identity=expected)
        profiler.emit_captured(captured['profiler'], phase='load', operation='reset',
            sequence=0, player_id=player_id, wall_seconds=captured['wall_seconds'],
            core_identity=captured['core_identity'])
        return True
    except BaseException:
        failed = True
        raise
    finally:
        try:
            delattr(owner.backend, '_command_load_profile')
        except BaseException:
            if not failed:
                raise


def _execute_xp1(saved, action, player_id, sequence, path):
    """Requery the native family immediately before the retained command call."""
    context = getattr(saved, '_xp2_diplomacy', None)
    if context is not None:
        if action.get('kind') != 'diplomacy_response':
            return dict(status='refused', reason='xp2_diplomacy_response_pending',
                        requested_action=action)
        from civ6_host.runtime.xp2_diplomacy import respond
        effect = respond(saved, action, saved.continuation.observation)
        if (type(effect) is not dict or effect.get('requested_action') != action
                or effect.get('status') not in ('completed', 'refused')):
            raise RuntimeError('Saved diplomacy response returned another action or status')
        reason = effect.get('reason')
        if effect['status'] == 'refused' and reason is None:
            reason = effect.get('refusal_code')
        if reason is not None and type(reason) is not str:
            raise RuntimeError('Saved diplomacy response returned an invalid refusal reason')
        return dict(status=effect['status'], reason=reason, requested_action=action)
    if action.get('kind') == 'diplomacy_response':
        return dict(status='refused', reason='xp2_diplomacy_context_not_retained',
                    requested_action=action)
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.contracts.city_state_levies import ACTION as LEVY_MILITARY
    from civ6_host.runtime.xp1_session_view import read, read_turn_preflight
    from civ6_host.runtime.xp1_session_inputs import _write_once
    from copy import deepcopy
    turn_action = action['kind'] in ('end_turn', 'force_end_turn', 'unready_turn')
    placement_action = action['kind'] in ('production_placement','production_resume')
    production_action = action['kind'] == 'production' or placement_action
    prior_production = (deepcopy(saved.continuation.explicit_production_snapshot)
                        if production_action else None)
    prior_placements = deepcopy(saved.continuation.explicit_placements) if placement_action else None
    queue_action = action['kind'] in ('queue_append', 'queue_remove', 'queue_swap')
    prior_queues = deepcopy(saved.continuation.explicit_production_queues) if queue_action else None
    city_action=action['kind'] in ('city_focus','city_citizen')
    if city_action:
        from civ6_host.runtime.expansion_city_controls import catalogue_snapshot
        prior_city=catalogue_snapshot(saved)
    shot_action = action['kind'] in ('city_range_attack', 'district_range_attack')
    prior_shot = ((deepcopy(saved.continuation.explicit_ranged_shots[action['kind']]),
                   deepcopy(saved.continuation.explicit_city_shot_defenses))
                  if shot_action else None)
    attack_action = action['kind']=='unit_attack'
    occupation_action = action['kind'] == 'resolve_captured_city'
    xp2_levy_action = action['kind'] == LEVY_MILITARY and saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
    prior_levy = (getattr(saved.continuation, 'explicit_city_state_levies', None)
                  if xp2_levy_action else None)
    prior_occupation = (deepcopy(saved.continuation.explicit_captured_city)
                        if occupation_action else None)
    if attack_action:
        from civ6_host.contracts.capability_unit_attacks import project_cities
        shape = saved.continuation.observation
        prior_combat = (deepcopy(saved.continuation.explicit_combat_units),
                        project_cities(saved.continuation.explicit_combat_cities, shape['width'], shape['height']))
    from civ6_host.contracts.capability_world_input import WORLD_KINDS
    from civ6_host.contracts.archaeology import EXCAVATE, KIND as CHOOSE_ARTIFACT_ORIGIN
    world_action = action['kind'] in WORLD_KINDS or action['kind'] == 'world_war_response'
    prior_world=(deepcopy(saved.continuation.explicit_world_input) if world_action else None)
    origin_action = action['kind'] == CHOOSE_ARTIFACT_ORIGIN
    excavation_action = action['kind'] == EXCAVATE
    prior_archaeology = getattr(saved, 'explicit_archaeology', None) if origin_action else None
    if (turn_action and saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
            and saved.continuation.world_input_prompts.get(player_id) is None):
        observed, available = read_turn_preflight(saved, player_id, action['kind'])
        available = available and action == {'kind': action['kind']}
    else:
        _, observed, decisions = read(saved, player_id, sequence)
        from civ6_host.contracts.world_congress import ACTION_FIELDS as CONGRESS_ACTION_FIELDS
        if action['kind'] in CONGRESS_ACTION_FIELDS:
            from civ6_host.runtime.xp2_world_congress import _admit
            try:
                _admit(decisions.get('world_congress'), action)
                available = True
            except (ValueError, TypeError):
                available = False
        elif action['kind'] == 'policies':
            from civ6_host.contracts.policies import choose, PolicyAssignmentUnavailable
            from civ6_host.contracts import network_turn as policy_contract
            policy_catalogue = decisions.get('policies')
            available = False
            if policy_catalogue is not None and policy_catalogue['reason'] == 'available':
                try:
                    chosen = choose(policy_catalogue['slots'],
                        [value & 0xffffffff for _, value in action['candidate']['assignments']],
                        player_id, observed['turn'], allow_relocation=(decisions['schema'] in
                            policy_contract.POLICY_RELOCATION_CAPABILITY_SCHEMAS),
                        allow_unchanged=(decisions['schema'] in policy_contract.POLICY_RECONFIRM_CAPABILITY_SCHEMAS))
                    available = chosen == action['candidate']
                except PolicyAssignmentUnavailable:
                    pass
        elif action['kind'] == 'found_custom_religion':
            from civ6_host.contracts import religion_custom_names as names
            names.validate_action(action)
            template = {key: action[key] for key in ('kind','index','hash')}
            state = decisions.get('religion_custom_names')
            available = False
            if state is not None and any(row['action'] == template for row in decisions['candidates']):
                parameters = {'name': action['custom_name']} if state['rename_allowed'] else None
                try:
                    available = names.choose(state, template, parameters) == action
                except ValueError:
                    pass
        elif action['kind'] == 'confirm_dedications':
            from civ6_host.contracts import dedications, network_turn
            try:
                available = network_turn.select_capability(decisions, {
                    'decision_id': decisions['decision_id'],
                    'candidate_id': network_turn.digest(dedications.CANDIDATE),
                    'parameters': {'indices': action['indices']},
                }) == action
            except ValueError:
                available = False
        else:
            available = any(row['action'] == action for row in decisions['candidates'])
    if not available:
        return dict(status='refused', reason='native_action_no_longer_available',
                    requested_action=action)
    if (production_action
            and prior_production != saved.continuation.explicit_production_snapshot):
        return dict(status='refused', reason='native_production_state_changed', requested_action=action)
    if placement_action and prior_placements != saved.continuation.explicit_placements:
        return dict(status='refused',reason='native_placement_state_changed',requested_action=action)
    if world_action and prior_world!=saved.continuation.explicit_world_input:
        return dict(status='refused',reason='native_world_input_state_changed',requested_action=action)
    if origin_action and (prior_archaeology is None or prior_archaeology != saved.explicit_archaeology):
        return dict(status='refused', reason='native_artifact_origin_choice_changed', requested_action=action)
    if queue_action and prior_queues != saved.continuation.explicit_production_queues:
        return dict(status='refused',reason='native_production_queue_state_changed',requested_action=action)
    if attack_action and prior_combat != (saved.continuation.explicit_combat_units,
             project_cities(saved.continuation.explicit_combat_cities,observed['width'],observed['height'])):
        return dict(status='refused',reason='native_combat_state_changed',requested_action=action)
    if occupation_action and prior_occupation != saved.continuation.explicit_captured_city:
        return dict(status='refused', reason='native_captured_city_state_changed', requested_action=action)
    if xp2_levy_action and prior_levy != saved.continuation.explicit_city_state_levies:
        return dict(status='refused', reason='native_city_state_levy_offer_changed', requested_action=action)
    if shot_action and prior_shot != (saved.continuation.explicit_ranged_shots[action['kind']],
                                      saved.continuation.explicit_city_shot_defenses):
        return dict(status='refused', reason='native_ranged_shot_state_changed', requested_action=action)
    if city_action and prior_city!=catalogue_snapshot(saved):
        return dict(status='refused',reason='native_city_control_state_changed',requested_action=action)
    # The command adapter retains its own current public before-state. A query
    # cannot move the world; detect unexpected advancement before dispatch.
    if saved.continuation.observation != observed:
        raise RuntimeError('XP1 command before-state changed outside the retained continuation')
    saved.emit('before_xp1_saved_unit_commands', protocol_sequence=sequence+1,
               public_runtime_admitted=False)
    result = saved.execute(action)
    if result['action'] != action:
        raise RuntimeError('XP1 native command receipt identifies another choice')
    retained = _retain_xp2_diplomacy_if_ready(saved)
    if action['kind'] == 'world_war_response' and result['effect'].get('status') == 'completed':
        if result['effect'].get('pending_statement_retained') is not True and retained:
            result['effect']['pending_statement_retained'] = True
    saved.emit('xp1_saved_unit_commands_returned',
        protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/
            ('command-result-' + str(sequence+1) + '.json'), result))
    if not retained and getattr(saved, 'world_congress_diagnostic', False):
        effect = result.get('effect')
        partial = (type(effect) is dict and type(effect.get('receipt')) is dict
                   and effect['receipt'].get('partial_submission') is True)
        if partial:
            raise RuntimeError('Congress partial native journal retained; further model decisions refused')
        automatic = saved.advance_congress_empty(sequence + 1)
        if automatic is not None:
            saved.emit('xp2_congress_automatic_phase_returned', protocol_sequence=sequence+1,
                receipt=_write_once(_Path(path).resolve().parent/
                    ('congress-automatic-result-'+str(sequence+1)+'.json'), automatic))
    from civ6_host.contracts.world_congress import ACTION_FIELDS as CONGRESS_ACTION_FIELDS
    if action['kind'] in CONGRESS_ACTION_FIELDS:
        effect = result['effect']
        receipt = effect.get('receipt') if type(effect) is dict else None
        if (type(receipt) is not dict or receipt.get('action') != action
                or effect.get('status') not in ('completed', 'refused', 'pending')):
            raise RuntimeError('Congress confirmation returned a foreign result')
        if effect['status'] == 'completed' and (action['kind'] != 'congress_open'
                or receipt.get('local_presentation_completed') is not True
                or receipt.get('simulation_request_issued') is not False):
            raise RuntimeError('Congress native application has no qualified completion readback')
        if effect['status'] == 'pending' and receipt.get('native_archive_delivered') is not True:
            raise RuntimeError('Congress pending result lacks its native journal')
        return dict(status=effect['status'], reason=effect.get('refusal_code'), requested_action=action)
    if turn_action:
        if result['effect']['requested_action']!=action:
            raise RuntimeError('XP1 turn effect identifies another request')
        return result['effect']
    if action['kind'] == 'spy_completion_dismiss':
        effect = result['effect']
        receipt = effect.get('receipt') if type(effect) is dict else None
        if (type(receipt) is not dict or effect.get('status') != 'completed'
                or receipt.get('action') != action
                or receipt.get('local_presentation_completed') is not True
                or receipt.get('simulation_request_issued') is not False
                or receipt.get('native_archive_delivered') is not False):
            raise RuntimeError('Spy completion dismissal lacks its exact local presentation receipt')
        return dict(status='completed', reason=None, requested_action=action)
    from civ6_host.contracts.espionage import ACTION_FIELDS as ESPIONAGE_ACTION_FIELDS
    if action['kind'] in ESPIONAGE_ACTION_FIELDS or action['kind'] == 'spy_renew':
        effect = result['effect']
        statuses = (('completed', 'refused', 'pending') if action['kind'] == 'spy_renew'
                    else ('completed', 'refused', 'submitted', 'pending'))
        if (type(effect) is not dict
                or effect.get('status') not in statuses
                or type(effect.get('receipt')) is not dict
                or effect['receipt'].get('action') != action):
            raise RuntimeError('XP2 espionage did not return the requested native receipt')
        if effect['status'] != 'refused' and effect['receipt'].get('native_archive_delivered') is not True:
            raise RuntimeError('XP2 espionage accepted a choice without native archive delivery')
        if effect['status'] == 'completed' and effect['receipt'].get('native_effect_readback') is not True:
            raise RuntimeError('XP2 espionage completion lacks native effect readback')
        reason = effect.get('refusal_code')
        if reason is not None and type(reason) is not str:
            raise RuntimeError('XP2 espionage returned an invalid refusal reason')
        return dict(status=effect['status'], reason=reason, requested_action=action)
    from civ6_host.runtime.xp1_continuation import TRADE_KINDS
    if action['kind'] in TRADE_KINDS:
        effect = result['effect']
        if (effect['status'] != 'completed' or effect['receipt']['action'] != action
                or effect['receipt']['native_effect_readback'] is not True):
            raise RuntimeError('Trade did not return the requested native effect')
        return dict(status='completed', reason=None, requested_action=action)
    if world_action or action['kind'] == 'diplomacy_initiate':
        effect=result['effect']
        if effect['status'] not in ('completed','refused'):
            raise RuntimeError('XP1 world-input result has an unqualified status')
        return dict(status=effect['status'],reason=effect['refusal_code'],requested_action=action)
    if action['kind'] == 'unit_formation':
        effect = result['effect']
        receipt = effect['receipt']
        if (effect['status'] not in ('completed', 'refused') or receipt['action'] != action
                or receipt['native_archive_delivered'] is not True
                or receipt['native_effect_readback'] is not (effect['status'] == 'completed')):
            raise RuntimeError('Formation result lacks the requested native readback')
        return dict(status=effect['status'], reason=effect['refusal_code'], requested_action=action)
    if action['kind'] == 'confirm_dedications':
        effect = result['effect']
        receipt = effect['receipt']
        if (effect['status'] != 'completed' or receipt['action'] != action
                or receipt['native_archive_delivered'] is not True
                or receipt['native_effect_readback'] is not True
                or len(receipt['native_archive_sha256']) != len(action['indices'])):
            raise RuntimeError('Dedication confirmation lacks exact native archive and effect readback')
        return dict(status='completed', reason=None, requested_action=action)
    from civ6_host.contracts.city_buildings import GREAT_WORK_MOVE
    if action['kind'] == GREAT_WORK_MOVE:
        effect = result['effect']
        receipt = effect.get('receipt')
        if (effect['status'] == 'completed'
                and (type(receipt) is not dict or receipt.get('action') != action
                     or receipt.get('native_archive_delivered') is not True
                     or receipt.get('native_effect_readback') is not True)):
            raise RuntimeError('Great Work command lacks its exact archive and effect')
        if effect['status'] not in ('refused', 'completed'):
            raise RuntimeError('Unqualified Great Work command result')
        return dict(status=effect['status'], reason=effect['refusal_code'], requested_action=action)
    from civ6_host.contracts import air_operations, national_parks, rock_bands, unit_work
    if action['kind'] in (air_operations.KIND, unit_work.BUILD_ROUTE, national_parks.DESIGNATE, rock_bands.KIND):
        from civ6_host.runtime.xp2_air_operations import WAR_PENDING

        is_air = action['kind'] == air_operations.KIND
        if is_air:
            from civ6_host.runtime import xp2_air_operations as command
        elif action['kind'] == national_parks.DESIGNATE:
            from civ6_host.runtime import xp2_designate_park as command
        elif action['kind'] == rock_bands.KIND:
            from civ6_host.runtime import xp2_rock_bands as command
        else:
            from civ6_host.runtime import xp2_build_route as command

        effect = result['effect']
        status, reason = effect['status'], effect['refusal_code']
        if status == 'refused' and reason == command.REFUSED:
            return dict(status=status, reason=reason, requested_action=action)
        receipt = effect.get('receipt')
        archive = receipt.get('archive_sha256') if type(receipt) is dict else None
        if is_air and status == 'pending' and reason == WAR_PENDING and action['operation'] == air_operations.ATTACK:
            from civ6_host.contracts.war_confirmation import validate_prompt

            if (type(receipt) is not dict or set(receipt) != {'action', 'archive_sha256', 'war_prompt'}
                    or receipt['action'] != action or archive is not None
                    or validate_prompt(receipt['war_prompt'], player_id) !=
                       saved.continuation.world_input_prompts.get(player_id)):
                raise RuntimeError('Air attack lacks its exact pending war prompt')
            return dict(status=status, reason=reason, requested_action=action)
        if (status not in ('completed', 'submitted') or type(archive) is not str or len(archive) != 64
                or any(char not in '0123456789abcdef' for char in archive)
                or receipt.get('action') != action
                or receipt.get('effect_observed') is not (status == 'completed')
                or reason != (None if status == 'completed' else command.SUBMITTED)):
            raise RuntimeError('Native unit operation lacks its exact archive and observed result')
        response = dict(status=status, reason=reason, requested_action=action)
        if action['kind'] == rock_bands.KIND and status == 'completed':
            response['concert'] = rock_bands.validate_result(receipt['concert'], player_id,
                                                            observed['turn'], action)
        return response
    if origin_action or excavation_action:
        if excavation_action:
            from civ6_host.runtime.xp2_archaeology_excavation import REFUSED, UNCONFIRMED

            refusal_reasons = (REFUSED,)
            effect_fields = ('native_pending_created',)
        else:
            from civ6_host.runtime.xp2_archaeology import UNCONFIRMED

            refusal_reasons = ('native_artifact_origin_choice_changed', 'native_archaeology_actor_waiting')
            effect_fields = ('native_pending_cleared', 'native_artifact_creation_observed')

        effect = result['effect']
        status = effect['status']
        reason = effect['refusal_code']
        if status == 'refused' and reason in refusal_reasons:
            return dict(status=status, reason=reason, requested_action=action)
        receipt = effect.get('receipt')
        if (status not in ('completed', 'submitted') or type(receipt) is not dict or receipt.get('action') != action
                or receipt.get('native_archive_delivered') is not True
                or type(receipt.get('native_archive_sha256')) is not str
                or len(receipt['native_archive_sha256']) != 64
                or any(char not in '0123456789abcdef' for char in receipt['native_archive_sha256'])
                or any(type(receipt.get(field)) is not bool for field in effect_fields)
                or all(receipt[field] for field in effect_fields) != (status == 'completed')
                or reason != (None if status == 'completed' else UNCONFIRMED)):
            raise RuntimeError('Artifact command lacks its exact native archive and effect readback')
        return dict(status=status, reason=reason, requested_action=action)
    if getattr(saved, 'xp1_plot_purchase', False) and action['kind'] == 'purchase':
        receipt = result['effect']['receipt']
        effect = 'native_ownership_confirmed' if 'plot_id' in action else 'native_item_confirmed'
        if (receipt['action'] != action or receipt[effect] is not True
                or receipt['exact_treasury_debit_verified'] is not True):
            raise RuntimeError('Rise and Fall purchase lacks native acquisition and debit')
        return dict(status='completed', reason=None, requested_action=action)
    if getattr(saved, 'xp1_promotions', False) and action['kind'] == 'promote_unit':
        receipt = result['effect']['receipt']
        if receipt['action'] != action or receipt['native_promotion_acquired'] is not True:
            raise RuntimeError('Rise and Fall promotion lacks the requested native acquisition')
        return dict(status='completed',reason=None,requested_action=action)
    if getattr(saved,'xp1_unit_upgrades',False) and action['kind']=='upgrade_unit':
        receipt = result['effect']['receipt']
        if (receipt['action'] != action or receipt['native_unit_replaced'] is not True
                or receipt['exact_treasury_debit_verified'] is not True):
            raise RuntimeError('Rise and Fall upgrade lacks native replacement and debit')
        return dict(status='completed',reason=None,requested_action=action)
    from civ6_host.contracts import great_people_actions
    if action['kind'] in great_people_actions.KINDS:
        from civ6_host.runtime import xp1_great_people_commands as commands

        effect = result['effect']
        xp2 = saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
        reference = saved.backend.captured_bundle.reference if xp2 else None
        flag = 'xp2_great_people_actions' if xp2 else 'xp1_great_people_actions'
        if (getattr(saved, flag, False) is not True
                or (not xp2 and action['kind'] == commands.REJECT
                    and getattr(saved, 'xp1_great_people_reject', False) is not True)
                or type(effect) is not dict
                or effect.get('source_sha256') != commands.source_for(action, xp2=xp2, reference=reference)[1]
                or effect.get('observation') != result['observation_after']):
            raise RuntimeError('Great Person result lost its qualified source or actor observation')
        if effect.get('status') == 'refused':
            request = effect.get('request')
            if (effect.get('refusal_code') != 'native_great_person_can_start_false' or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False
                    or result['observation_before'] != result['observation_after']):
                raise RuntimeError('Great Person refusal lacks its native CanStart result')
            return dict(status='refused', reason=effect['refusal_code'], requested_action=action)
        receipt = effect.get('effect')
        after = result['observation_after']
        if action['kind'] == commands.REJECT:
            before = result['observation_before']
            if (effect.get('status') != 'completed' or effect.get('action') != action or type(receipt) is not dict
                    or any(type(receipt.get(k)) is not int for k in ('individual_index','class_index','player_id',
                        'turn','cost','own_receipts_before','own_receipts_after'))
                    or receipt['individual_index'] != action['individual_index'] or receipt['cost'] != action['cost']
                    or (receipt['player_id'],receipt['turn']) != (after['player_id'],after['turn'])
                    or (before['player_id'],before['turn']) != (after['player_id'],after['turn'])
                    or receipt['own_receipts_before'] < 0
                    or receipt['own_receipts_after'] != receipt['own_receipts_before']
                    or {row['id'] for row in before['units']} != {row['id'] for row in after['units']}
                    or any(before['economy'][k] != after['economy'][k] for k in ('gold','faith'))
                    or type(receipt.get('archive_sha256')) is not str or len(receipt['archive_sha256']) != 64
                    or any(c not in '0123456789abcdef' for c in receipt['archive_sha256'])
                    or (receipt.get('operation'),receipt.get('parameters')) != commands._operation(action)
                    or type(receipt.get('size_bytes')) is not int or receipt['size_bytes'] != 46):
                raise RuntimeError('Great Person rejection lacks its exact archive and unchanged grant state')
            points = [receipt.get(k) for k in ('points_before','points_after')]
            if any(type(v) not in (int,float) or not -8388608 <= v < 8388608 or int(v*256) != v*256 for v in points):
                raise RuntimeError('Great Person rejection points differ from native Q8 values')
            start,end = (int(v*256) for v in points)
            expected = max(0,commands._signed32(start + commands._signed32(-action['cost']*256)))
            if end not in ((start,expected) if expected > start else (expected,)):
                raise RuntimeError('Great Person rejection points differ from the verified native result')
            return dict(status='completed',reason=None,requested_action=action)
        if (effect.get('status') != 'completed' or effect.get('action') != action or type(receipt) is not dict
                or any(type(receipt.get(k)) is not int for k in ('individual_index','class_index','player_id',
                    'turn','unit_id','unit_type','instances_before','instances_after'))
                or receipt['individual_index'] != action['individual_index']
                or (receipt['player_id'],receipt['turn']) != (after['player_id'],after['turn'])
                or receipt['instances_after'] != receipt['instances_before'] + 1
                or not any((row['id'],row['type'],row['owner']) ==
                    (receipt['unit_id'],receipt['unit_type'],receipt['player_id']) for row in after['units'])
                or receipt['unit_id'] in {row['id'] for row in result['observation_before']['units']}
                or type(receipt.get('archive_sha256')) is not str or len(receipt['archive_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in receipt['archive_sha256'])
                or (receipt.get('operation'), receipt.get('parameters')) != commands._operation(action)
                or receipt.get('size_bytes') != (46 if action['kind'] == commands.RECRUIT else 68)):
            raise RuntimeError('Great Person result lacks the exact native archive and own grant')
        if action['kind'] == commands.PATRONIZE:
            balance = commands._BALANCES[action['currency']]
            start, end = result['observation_before']['economy'][balance], after['economy'][balance]
            if (type(receipt.get('amount_paid')) is not int or receipt['amount_paid'] != action['cost']
                    or (receipt.get('balance_before'),receipt.get('balance_after')) != (start,end)
                    or start - end != action['cost']):
                raise RuntimeError('Great Person result lacks the exact patronage debit')
        return dict(status='completed', reason=None, requested_action=action)
    if action['kind']=='activate_prophet':
        from civ6_host.runtime.xp1_prophet_activation_source import source_for
        flag = 'xp2_prophet_activation' if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256 else 'xp1_prophet_activation'
        image = getattr(saved.backend.core,'_civ6_host_execution_image',None)
        effect=result['effect']
        if (getattr(saved,flag,False) is not True
                or getattr(image,'reference_core_sha256',None)!=saved.backend.load_abi.core_sha256
                or type(effect) is not dict or effect.get('source_sha256') != source_for(image)[1]):
            raise RuntimeError('Prophet activation lost its exact native source identity')
        if effect.get('status')=='refused':
            request=effect.get('request')
            if (effect.get('refusal_code')!='native_prophet_can_start_false' or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False
                    or request.get('request_submitted') is not False):
                raise RuntimeError('Prophet activation refusal lacks its native CanStart result')
            return dict(status='refused',reason=effect['refusal_code'],requested_action=action)
        site=effect.get('founding_site')
        if (effect.get('status')!='completed'
                or any(type(effect.get(k)) is not int or effect[k]!=action[k] for k in ('unit_id','x','y'))
                or type(site) is not dict or set(site)!= {'player','type','id'}
                or any(type(site[k]) is not int for k in site)
                or site['player']!=saved.continuation.observation['player_id']
                or site['type']!=2 or not 0<=site['id']<=0x7fffffff):
            raise RuntimeError('Prophet activation result lacks the requested unit and founding site')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind'] in ('spread_religion','evangelize_belief','launch_inquisition','remove_heresy'):
        from civ6_host.runtime import xp1_religious_unit_operations as religious
        from civ6_host.contracts import religious_unit_operations as public
        effect=result['effect']
        before,after=result['observation_before'],result['observation_after']
        flag = ('xp2_religious_unit_operations' if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
                else 'xp1_religious_unit_operations')
        image = getattr(saved.backend.core,'_civ6_host_execution_image',None)
        if (getattr(saved,flag,False) is not True
                or getattr(image,'reference_core_sha256',None)!=saved.backend.load_abi.core_sha256
                or type(effect) is not dict or effect.get('source_sha256')!=religious.source_for(image)[1]
                or effect.get('action')!=action or effect.get('observation')!=after or before!=observed
                or (before['player_id'],before['turn'])!=(after['player_id'],after['turn'])):
            raise RuntimeError('Religious unit operation lost its source, selected action or actor observation')
        try:
            public.validate_action(effect['action'])
        except (ValueError,TypeError,KeyError) as error:
            raise RuntimeError('Religious unit operation receipt has a malformed selected action') from error
        if effect.get('status')=='refused':
            request=effect.get('request')
            if (effect.get('refusal_code')!=religious.REFUSED or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False
                    or before!=after):
                raise RuntimeError('Religious unit operation refusal lacks its native CanStart result')
            return dict(status='refused',reason=religious.REFUSED,requested_action=action)
        receipt=effect.get('receipt')
        if effect.get('status') not in ('completed','submitted') or type(receipt) is not dict:
            raise RuntimeError('Religious unit operation lacks a processed command receipt')
        try:
            confirmed=religious.confirmation(receipt,action,before,after)
        except (ValueError,TypeError,KeyError) as error:
            raise RuntimeError('Religious unit operation has malformed native effect evidence') from error
        if type(confirmed) is not bool:
            raise RuntimeError('Religious unit operation completion predicate is not a native evidence boolean')
        status='completed' if confirmed else 'submitted'
        reason=None if confirmed else religious.UNCONFIRMED
        if effect['status']!=status or effect.get('refusal_code')!=reason:
            raise RuntimeError('Religious unit operation confused processing with a confirmed effect')
        return dict(status=status,reason=reason,requested_action=action)
    if action['kind'] == 'activate_great_person':
        from civ6_host.runtime import xp1_great_person_activation as activation
        from civ6_host.contracts import great_person_activation as public
        effect = result['effect']
        before,after = result['observation_before'],result['observation_after']
        profile = activation.selected_source(saved)
        if (not activation.enabled(saved)
                or type(effect) is not dict or effect.get('source_sha256') != profile.SOURCE[1]
                or effect.get('observation') != after
                or (before['player_id'],before['turn']) != (after['player_id'],after['turn'])):
            raise RuntimeError('Great Person activation lost its source or actor observation')
        if before != observed:
            raise RuntimeError('Great Person activation receipt changed its queried before-state')
        if effect.get('status') == 'refused':
            request = effect.get('request')
            if (effect.get('refusal_code') != activation.REFUSED or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False
                    or before != after):
                raise RuntimeError('Great Person activation refusal lacks its native CanStart result')
            return dict(status='refused',reason=effect['refusal_code'],requested_action=action)
        receipt = effect.get('receipt')
        if (effect.get('status') not in ('completed','submitted') or type(receipt) is not dict
                or any(type(effect.get(k)) is not int or effect[k] != action[k] for k in ('unit_id','x','y'))
                or any(type(effect.get(k)) is not int or not 0 <= effect[k] <= 0x7fffffff
                       for k in ('individual_index','class_index'))
                or type(effect.get('charges_before')) is not int or not -0x80000000 <= effect['charges_before'] <= 0x7fffffff
                or type(effect.get('unit_consumed')) is not bool
                or (effect.get('charges_after') is None) != effect['unit_consumed']
                or not effect['unit_consumed'] and (type(effect.get('charges_after')) is not int
                    or not -0x80000000 <= effect['charges_after'] <= 0x7fffffff)
                or receipt.get('native_archive_delivered') is not True or receipt.get('native_command_processed') is not True
                or type(receipt.get('size_bytes')) is not int or receipt['size_bytes'] != 20
                or type(receipt.get('normalized_command_index')) is not int or not 0 <= receipt['normalized_command_index'] <= 0x7fffffff
                or type(receipt.get('command_hash')) is not int or receipt['command_hash'] != public.OPERATION
                or type(receipt.get('parameters')) is not dict or receipt['parameters'] != {}
                or type(receipt.get('post_command_sequence')) is not int or not 1 <= receipt['post_command_sequence'] <= 0x7fffffff
                or type(receipt.get('archive_sha256')) is not str or len(receipt['archive_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in receipt['archive_sha256'])):
            raise RuntimeError('Great Person activation lacks exact command processing and charge readback')
        old,new = receipt.get('unit_before'),receipt.get('unit_after')
        if type(old) is not dict or (new is None) != effect['unit_consumed']:
            raise RuntimeError('Great Person activation has a malformed own-unit receipt')
        try:
            for observation,rows in ((before,[old]),(after,[] if new is None else [new])):
                public.project(dict(player_id=observation['player_id'],current_game_turn=observation['turn'],
                                    operation=public.OPERATION,units=rows),observation['player_id'],observation['turn'],
                               observation=observation)
        except (ValueError,TypeError,KeyError) as error:
            raise RuntimeError('Great Person activation receipt differs from its public own-unit view') from error
        identity=('unit_id','individual_index','class_index')
        if (any(old[k] != effect[k] for k in (*identity,'x','y')) or old['charges'] != effect['charges_before']
                or not old['visible'] or not old['available']
                or (new is None and any(row['id']==effect['unit_id'] for row in after['units']))
                or (new is not None and (any(new[k] != effect[k] for k in identity)
                    or new['charges'] != effect['charges_after']))):
            raise RuntimeError('Great Person activation result identifies another unit or charge state')
        basis=activation.confirmation(receipt,pid=before['player_id'],unit_id=effect['unit_id'],
            cities=before['cities'],charges_before=effect['charges_before'],
            charges_after=effect['charges_after'],unit_consumed=effect['unit_consumed'],profile=profile)
        expected_status='completed' if basis else 'submitted'
        reason=None if basis else activation.UNCONFIRMED
        if (receipt.get('effect_confirmed') is not (basis is not None)
                or receipt.get('confirmation_basis') != basis
                or effect['status'] != expected_status or effect.get('reason') != reason):
            raise RuntimeError('Great Person activation confused command processing with a confirmed effect')
        return dict(status=expected_status,reason=reason,requested_action=action)
    if action['kind'] == 'found_custom_religion':
        from civ6_host.runtime import xp1_religion_custom_names as names
        effect = result['effect']
        before,after = result['observation_before'],result['observation_after']
        if (getattr(saved,'xp1_religion_custom_names',False) is not True
                or getattr(saved,'xp1_religion_founding',False) is not True
                or type(effect) is not dict or effect.get('source_sha256') != names.SOURCE[1]
                or effect.get('observation') != after
                or (before['player_id'],before['turn']) != (after['player_id'],after['turn'])):
            raise RuntimeError('Custom religion result lost its qualified source or actor observation')
        if effect.get('status') == 'refused':
            code = effect.get('refusal_code')
            if before != after:
                raise RuntimeError('Refused custom religion naming changed the player observation')
            if code == names.UI_INVALID:
                if 'request' not in effect or effect['request'] is not None:
                    raise RuntimeError('Custom religion input refusal falsely identifies a native request')
            elif code == names.NATIVE_REFUSED:
                request = effect.get('request')
                if (type(request) is not dict or request.get('can_start') is not False
                        or request.get('request_invoked') is not False):
                    raise RuntimeError('Custom religion refusal lacks its native CanStart result')
            else:
                raise RuntimeError('Custom religion refusal has an unknown reason')
            return dict(status='refused',reason=code,requested_action=action)
        if (effect.get('status') != 'completed'
                or type(effect.get('selected_index')) is not int or effect['selected_index'] != action['index']
                or type(effect.get('selected_hash')) is not int or effect['selected_hash'] != action['hash']
                or type(effect.get('custom_name')) is not str or effect['custom_name'] != action['custom_name']):
            raise RuntimeError('Custom religion result differs from the exact selected icon and name')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind']=='found_religion':
        from civ6_host.runtime.xp1_religion_founding_source import source_for
        flag = 'xp2_religion_founding' if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256 else 'xp1_religion_founding'
        image = getattr(saved.backend.core,'_civ6_host_execution_image',None)
        effect=result['effect']
        if (getattr(saved,flag,False) is not True
                or getattr(image,'reference_core_sha256',None)!=saved.backend.load_abi.core_sha256
                or type(effect) is not dict or effect.get('source_sha256') != source_for(image)[1]):
            raise RuntimeError('Religion founding result lost its exact native source identity')
        if effect.get('status')=='refused':
            if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256:
                raise RuntimeError('Gathering Storm direct founding request has no CanStart refusal contract')
            request=effect.get('request')
            if (effect.get('refusal_code')!='native_religion_foundation_can_start_false' or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False):
                raise RuntimeError('Religion founding refusal lacks its native CanStart result')
            return dict(status='refused',reason=effect['refusal_code'],requested_action=action)
        if (effect.get('status')!='completed' or type(effect.get('selected_index')) is not int
                or type(effect.get('selected_hash')) is not int
                or effect['selected_index']!=action['index'] or effect['selected_hash']!=action['hash']):
            raise RuntimeError('Religion founding result lacks the requested native religion')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind']=='add_belief':
        from civ6_host.runtime.xp1_religion_beliefs_source import source_for
        flag = 'xp2_religion_beliefs' if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256 else 'xp1_religion_beliefs'
        image = getattr(saved.backend.core,'_civ6_host_execution_image',None)
        effect=result['effect']
        if (getattr(saved,flag,False) is not True
                or getattr(image,'reference_core_sha256',None)!=saved.backend.load_abi.core_sha256
                or type(effect) is not dict or effect.get('source_sha256') != source_for(image)[1]):
            raise RuntimeError('Belief result lost its exact native source identity')
        if effect.get('status')=='refused':
            if saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256:
                raise RuntimeError('Gathering Storm direct belief request has no CanStart refusal contract')
            request=effect.get('request')
            if (effect.get('refusal_code')!='native_belief_can_start_false' or type(request) is not dict
                    or request.get('can_start') is not False or request.get('request_invoked') is not False):
                raise RuntimeError('Belief refusal lacks its native CanStart result')
            return dict(status='refused',reason=effect['refusal_code'],requested_action=action)
        if (effect.get('status')!='completed' or type(effect.get('selected_index')) is not int
                or type(effect.get('selected_hash')) is not int or type(effect.get('selected_class')) is not str
                or any(effect.get('selected_'+key)!=action[key] for key in ('index','hash','class'))):
            raise RuntimeError('Belief result lacks the requested native acquisition')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind']=='pantheon':
        from civ6_host.runtime.xp1_pantheon_source import source_for
        xp2 = saved.backend.load_abi.core_sha256 == XP2_CORE_SHA256
        flag = 'xp2_pantheon' if xp2 else 'xp1_pantheon'
        image = getattr(saved.backend.core,'_civ6_host_execution_image',None)
        effect = result['effect']
        if (getattr(saved,flag,False) is not True
                or getattr(image,'reference_core_sha256',None) != saved.backend.load_abi.core_sha256
                or type(effect) is not dict or effect.get('source_sha256') != source_for(image)[1]):
            raise RuntimeError('Pantheon result lost its exact native source identity')
        if effect.get('status') == 'refused':
            if xp2:
                raise RuntimeError('Gathering Storm direct pantheon request has no CanStart refusal contract')
            request = effect.get('request')
            if (effect.get('refusal_code') != 'native_pantheon_can_start_false'
                    or type(request) is not dict or request.get('can_start') is not False
                    or request.get('request_invoked') is not False):
                raise RuntimeError('Pantheon refusal lacks its native CanStart result')
            return dict(status='refused',reason=effect['refusal_code'],requested_action=action)
        if (effect.get('status') != 'completed'
                or type(effect.get('selected_index')) is not int or type(effect.get('selected_hash')) is not int
                or effect.get('selected_index') != action['index']
                or effect.get('selected_hash') != action['hash']):
            raise RuntimeError('Pantheon result lacks the requested native belief acquisition')
        return dict(status='completed',reason=None,requested_action=action)
    if getattr(saved, 'xp1_government', False) and action['kind'] in ('government', 'retain_government', 'policies'):
        effect = result['effect']['effect']
        if action['kind'] == 'policies':
            if (effect.get('native_request_delivered') is not True
                    or effect.get('confirmation_verified_by') != 'slot_readback'):
                raise RuntimeError('Policy result lacks the selected native slot readback')
        elif (effect.get('confirmed') is not True
                or effect.get('current_government_index') != action['index']):
            raise RuntimeError('Government result lacks the selected native readback')
        return dict(status='completed', reason=None, requested_action=action)
    if action['kind']=='unit_order':
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 unit-order result has no matching native delivery')
        return dict(status='completed',reason=None,requested_action=action)
    if attack_action:
        from civ6_host.runtime.xp2_unit_attack_source import (
            CURRENT_XP2_NO_EFFECT, CURRENT_XP2_RANGE_SUBMITTED,
        )
        effect=result['effect']
        reason=effect.get('refusal_code')
        if (effect['receipt']['action'] != action or
                (effect['status'], reason) not in (
                    ('completed', None), ('refused', CURRENT_XP2_NO_EFFECT),
                    ('submitted', CURRENT_XP2_RANGE_SUBMITTED))):
            raise RuntimeError('Attack result lacks the requested native disposition')
        return dict(status=effect['status'],reason=reason,requested_action=action)
    if occupation_action:
        effect = result['effect']
        if effect['status'] != 'completed' or effect['action'] != action:
            raise RuntimeError('Captured-city choice has no matching native effect')
        return dict(status='completed', reason=None, requested_action=action)
    if xp2_levy_action:
        effect = result['effect']['effect']
        archive_hash = effect.get('native_archive_sha256')
        quote, = (row for row in prior_levy['city_states'] if row['player_id'] == action['target_player_id'])
        if (effect['target_player_id'] != action['target_player_id']
                or effect['gold_spent'] != quote['gold_cost']
                or effect['native_effect_readback'] is not True or not effect['controlled_unit_ids']
                or type(archive_hash) is not str or len(archive_hash) != 64
                or any(c not in '0123456789abcdef' for c in archive_hash)):
            raise RuntimeError('Military levy has no matching native archive and effect')
        return dict(status='completed', reason=None, requested_action=action)
    if queue_action or placement_action or action['kind'] in ('city_focus','city_citizen'):
        effect=result['effect']
        if effect['status']!='completed' or effect['receipt']['action']!=action:
            raise RuntimeError('XP1 production queue has no matching native effect')
        return dict(status='completed',reason=None,requested_action=action)
    return dict(status='completed', reason=None, requested_action=action)


def _retain_xp2_diplomacy_if_ready(saved):
    """Join a delivered type-132 statement only after the owner is quiescent."""
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    if saved.backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        return False
    deferred = saved.prefix.deferred_events
    ledger = getattr(deferred, 'pending_diplomacy_statements', None)
    if type(ledger) is not list or not ledger:
        return False
    if getattr(deferred, 'diplomacy_statement_receiver', None) is not deferred:
        raise RuntimeError('Delivered XP2 diplomacy statement has no exact retained receiver')
    if saved.backend.busy or saved.backend.stage != 'xp1-continuation-ready':
        raise RuntimeError('XP2 diplomacy cannot be retained during an active transition')
    from civ6_host.runtime.xp2_diplomacy import retain
    return retain(saved)


def _advance_xp1(saved,sequence,path):
    from civ6_host.runtime.xp1_session_inputs import _write_once
    saved.emit('before_xp1_saved_turn_update',protocol_sequence=sequence+1)
    result=saved.advance()
    if result['action'] is not None or result['game_update_called'] is not True:
        raise RuntimeError('XP1 poll did not return the explicit native update receipt')
    saved.emit('xp1_saved_turn_update_returned',protocol_sequence=sequence+1,
        receipt=_write_once(_Path(path).resolve().parent/('update-result-'+str(sequence+1)+'.json'),result))


def _poll_xp1(saved, sequence, path):
    """Keep the shared LAN poll from advancing through a retained modal."""
    if getattr(saved, '_xp2_diplomacy', None) is not None:
        return False
    _advance_xp1(saved, sequence, path)
    if getattr(saved, 'world_congress_diagnostic', False):
        automatic = saved.advance_congress_empty(sequence + 1)
        if automatic is not None:
            from civ6_host.runtime.xp1_session_inputs import _write_once
            saved.emit('xp2_congress_automatic_phase_returned', protocol_sequence=sequence+1,
                receipt=_write_once(_Path(path).resolve().parent/
                    ('congress-automatic-result-'+str(sequence+1)+'.json'), automatic))
    return True


def _read_xp1_outcome(saved, player_id):
    """Read a fresh outcome, allowing only the exact retained modal context."""
    from civ6_host.runtime.xp1_session_result import read
    context = getattr(saved, '_xp2_diplomacy', None)
    if context is None:
        return read(saved, player_id=player_id, allow_inactive_observer=True)
    return read(saved, player_id=player_id, allow_diplomacy=True)


def main(path):
    from civ6_host.runtime.native.native_probe import Windows
    from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
    win = Windows()
    win.kernel.SetErrorMode(1 | 2 | 32768)
    if sys.stdin.buffer.readline(16) != b'go\n':
        return 2

    trace_records = 0
    trace_seconds = 0.0

    def emit(stage, **fields):
        nonlocal trace_records, trace_seconds
        started = perf_counter()
        print(json.dumps(dict(stage=stage, **fields)), flush=True)
        trace_records += 1
        trace_seconds += perf_counter() - started

    try:
        from civ6_host.runtime.resource_resolution import resolve_path
        from civ6_host.runtime.network_protocol import (
            NetworkProtocol, SCHEMA, CLOSURE_SCHEMA, validate_network_response)
        from civ6_host.runtime.native.native_saved_session import (
            validate_episode_budget_closure, stdout_limit_ceiling)
        closure = json.loads(resolve_path(_Path(path)).read_bytes())
        from civ6_host.runtime.player_views import validate_lan_views, publish_player_views
        lan_view_players = validate_lan_views(closure)
        secondary_reader = None
        secondary_units = closure.get('secondary_unit_commands', False)
        if type(secondary_units) is not bool or (secondary_units and not lan_view_players):
            raise ValueError('LAN secondary commands require the authenticated XP2 public views')
        if secondary_units:
            from civ6_host.contracts import capability_policies, captured_city, city_ranged
            from civ6_host.contracts import city_state_levies, envoys
            from civ6_host.contracts import government, network_turn, plot_purchases, policies, policy_unlock
            from civ6_host.contracts import unit_work as work_contract
            from civ6_host.contracts import unit_work_info as work_info_contract
            from civ6_host.contracts import unit_work_state as work_state_contract
            from civ6_host.runtime import captured_city_session, explicit_production_operation, xp1_choice_queries
            from civ6_host.runtime import xp1_action_transport, xp1_production_queue
            from civ6_host.runtime import xp2_lan_city_controls, xp2_lan_production, xp2_lan_production_queue
            from civ6_host.runtime import xp2_lan_research, xp2_lan_unit_commands, xp2_lan_world_input
            from civ6_host.runtime import xp2_lan_ranged_shots, xp2_plot_purchases
            from civ6_host.runtime import xp2_government, xp2_lan_government, xp2_policies, xp2_policy_unlock
            from civ6_host.runtime import xp1_city_state_levies, xp2_city_state_levies, xp2_envoys, xp2_lan_city_states
            from civ6_host.runtime import unit_work_info, unit_work_state, xp2_lan_unit_work
            from civ6_host.runtime import xp2_lan_unit_attacks
            from civ6_host.runtime import xp2_lan_unit_development, xp2_promotions, xp2_unit_upgrades
            from civ6_host.runtime.native import native_saved_captured_city, native_saved_combat
            from civ6_host.runtime.native import native_saved_city_shot, native_saved_district_shot
            from civ6_host.runtime.native import native_plot_purchases, native_saved_purchases
            from civ6_host.runtime.native import native_policy_actions
            from civ6_host.runtime.native import native_saved_unit_work
            from civ6_host.runtime.source_verification import file_sha256
            for module in (xp2_lan_unit_commands, xp2_lan_research, xp2_lan_production,
                           explicit_production_operation, xp1_choice_queries, network_turn,
                           xp1_action_transport, xp1_production_queue, xp2_lan_production_queue,
                           xp2_lan_city_controls, xp2_lan_world_input, xp2_lan_unit_development,
                           xp2_promotions, xp2_unit_upgrades, xp2_lan_unit_attacks, native_saved_combat,
                           captured_city, captured_city_session, native_saved_captured_city,
                           city_ranged, xp2_lan_ranged_shots, native_saved_city_shot, native_saved_district_shot,
                           plot_purchases, xp2_plot_purchases, native_plot_purchases, native_saved_purchases,
                           xp2_lan_government, xp2_government, xp2_policies, xp2_policy_unlock, native_policy_actions,
                           capability_policies, government, policies, policy_unlock,
                           city_state_levies, envoys, xp1_city_state_levies, xp2_city_state_levies,
                           xp2_envoys, xp2_lan_city_states, work_contract, unit_work_info, unit_work_state,
                           work_info_contract, work_state_contract, xp2_lan_unit_work, native_saved_unit_work):
                source = _Path(module.__file__).resolve()
                if closure['pins'].get(str(source)) != file_sha256(source):
                    raise ValueError('LAN secondary command source closure differs')
            secondary_reader = xp2_lan_unit_commands.read_reply
        budget = validate_episode_budget_closure(closure)
        xp1 = closure.get('input_profile') in ('xp1-lan','xp2-lan')
        from civ6_host.runtime.session_limits import standard_lifetime_limit
        if (closure.get('schema') != CLOSURE_SCHEMA or closure.get('input_profile') not in ('lan', 'xp1-lan','xp2-lan')
                or type(closure.get('lifetime_seconds')) is not int
                or not 1 <= closure['lifetime_seconds'] <= (600 if budget else standard_lifetime_limit(closure.get('input_profile')))
                or type(closure.get('stdout_limit_bytes')) is not int
                or not 1048576 <= closure['stdout_limit_bytes'] <= stdout_limit_ceiling(budget)
                or type(closure.get('rounds')) is not int
                or not 1 <= closure['rounds'] <= NetworkProtocol.max_round_limit
                or type(closure.get('privileged_critic_diagnostic', False)) is not bool
                or type(closure.get('foundation_legality_diagnostic', False)) is not bool
                or type(closure.get('governors_diagnostic', False)) is not bool
                or type(closure.get('diplomacy_overview_diagnostic', False)) is not bool
                or type(closure.get('trade_diagnostic', False)) is not bool
                or type(closure.get('standard_trade', False)) is not bool
                or type(closure.get('xp1_trade', False)) is not bool
                or type(closure.get('xp1_trade_overview', False)) is not bool
                or type(closure.get('xp1_government', False)) is not bool
                or type(closure.get('xp1_plot_purchase', False)) is not bool
                or type(closure.get('xp1_city_purchase', False)) is not bool
                or type(closure.get('xp1_faith_purchase', False)) is not bool
                or type(closure.get('xp1_city_buildings', False)) is not bool
                or type(closure.get('xp1_unit_work', False)) is not bool
                or type(closure.get('world_score', False)) is not bool
                or type(closure.get('xp2_archaeology', False)) is not bool
                or (closure.get('xp2_archaeology', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_archaeology_commands', False)) is not bool
                or (closure.get('xp2_archaeology_commands', False) and closure.get('xp2_archaeology') is not True)
                or type(closure.get('xp2_air_operations', False)) is not bool
                or (closure.get('xp2_air_operations', False)
                    and (closure['input_profile'] != 'xp2-lan' or closure.get('war_source_sha256') is None))
                or type(closure.get('xp2_build_route', False)) is not bool
                or (closure.get('xp2_build_route', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_designate_park', False)) is not bool
                or (closure.get('xp2_designate_park', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_rock_bands', False)) is not bool
                or (closure.get('xp2_rock_bands', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_extra_unit_orders', False)) is not bool
                or (closure.get('xp2_extra_unit_orders', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('expansion_city_growth', False)) is not bool
                or type(closure.get('expansion_city_loyalty', False)) is not bool
                or type(closure.get('expansion_national_parks', False)) is not bool
                or type(closure.get('xp1_promotions', False)) is not bool
                or type(closure.get('xp1_unit_upgrades', False)) is not bool
                or type(closure.get('xp1_pantheon', False)) is not bool
                or type(closure.get('xp1_religion_beliefs', False)) is not bool
                or type(closure.get('xp1_religion_founding', False)) is not bool
                or type(closure.get('xp1_religion_custom_names', False)) is not bool
                or (closure.get('xp1_religion_custom_names', False)
                    and (closure.get('xp1_religion_founding', False) is not True
                         or closure['input_profile'] != 'xp1-lan'))
                or type(closure.get('xp1_prophet_activation', False)) is not bool
                or type(closure.get('xp1_great_person_activation', False)) is not bool
                or type(closure.get('xp1_religious_unit_operations', False)) is not bool
                or type(closure.get('xp2_religious_unit_operations', False)) is not bool
                or type(closure.get('xp2_prophet_activation', False)) is not bool
                or (closure.get('xp2_prophet_activation', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_religion_founding', False)) is not bool
                or (closure.get('xp2_religion_founding', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_religion_beliefs', False)) is not bool
                or (closure.get('xp2_religion_beliefs', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_pantheon', False)) is not bool
                or (closure.get('xp2_pantheon', False) and closure['input_profile'] != 'xp2-lan')
                or (closure.get('xp2_religious_unit_operations', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp1_city_religion_details', False)) is not bool
                or type(closure.get('xp2_city_religion_details', False)) is not bool
                or (closure.get('xp2_city_religion_details', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_great_people', False)) is not bool
                or (closure.get('xp2_great_people', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_great_people_actions', False)) is not bool
                or (closure.get('xp2_great_people_actions', False) and closure.get('xp2_great_people') is not True)
                or type(closure.get('xp2_great_person_activation', False)) is not bool
                or (closure.get('xp2_great_person_activation', False) and closure['input_profile'] != 'xp2-lan')
                or type(closure.get('xp2_city_buildings', False)) is not bool
                or (closure.get('xp2_city_buildings', False) and closure['input_profile'] != 'xp2-lan')
                or (closure.get('xp1_city_religion_details', False) and closure['input_profile'] != 'xp1-lan')
                or (closure.get('xp1_religious_unit_operations', False) and closure['input_profile'] != 'xp1-lan')
                or (closure.get('xp1_great_person_activation', False) and closure['input_profile'] != 'xp1-lan')
                or type(closure.get('xp1_great_people', False)) is not bool
                or type(closure.get('xp1_great_people_actions', False)) is not bool
                or type(closure.get('xp1_great_people_reject', False)) is not bool
                or (closure.get('xp1_great_people_reject', False)
                    and (closure.get('xp1_great_people_actions', False) is not True
                         or closure.get('xp1_great_people', False) is not True
                         or closure['input_profile'] != 'xp1-lan'))
                or (closure.get('xp1_great_people_actions', False)
                    and (closure.get('xp1_great_people', False) is not True or closure['input_profile'] != 'xp1-lan'))
                or type(closure.get('unit_formations', False)) is not bool
                or type(closure.get('stock_dedications', False)) is not bool
                or type(closure.get('city_state_levies', False)) is not bool
                or type(closure.get('espionage_diagnostic', False)) is not bool
                or type(closure.get('world_congress_diagnostic', False)) is not bool
                or type(closure.get('world_congress_review_diagnostic', False)) is not bool
                or type(closure.get('trade_overview_ui_selected', False)) is not bool
                or type(closure.get('command_profile_diagnostic', False)) is not bool
                or type(closure.get('checkpoint_on_close', False)) is not bool
                or closure.get('official_bundle') is None):
            raise ValueError('Unsupported bounded LAN closure')
        if closure.get('command_profile_diagnostic', False) and (
                closure['input_profile'] != 'xp2-lan' or 'execution_image' not in closure):
            raise ValueError('Command profiling requires the explicit XP2 image')
        if closure.get('city_state_levies', False) and closure['input_profile'] != 'xp2-lan':
            raise ValueError('Military levies cannot fall back to another session profile')
        foundation_legality = None
        if closure.get('foundation_legality_diagnostic', False) or closure.get('governors_diagnostic', False):
            from civ6_host.runtime.captured_session_profile import require_bbg_capture
            from civ6_host.runtime.execution_images import from_identity
            family_image = (from_identity(closure['execution_image']) if 'execution_image' in closure else None)
            if closure['input_profile'] != 'xp2-lan':
                raise ValueError('BBG family diagnostics require the XP2 input profile')
            require_bbg_capture(closure['official_bundle'], execution_image=family_image)
        if closure.get('foundation_legality_diagnostic', False):
            from civ6_host.runtime.xp2_foundation_legality import emit_readback as foundation_legality
        if closure.get('diplomacy_overview_diagnostic', False) and (
                closure['input_profile'] != 'xp2-lan'
                or not (closure.get('governors_diagnostic') is True or closure.get('standard_trade') is True)
                or 'execution_image' not in closure
                or closure.get('war_source_sha256') is None):
            raise ValueError('Initial diplomacy cannot fall back to another session profile')
        if closure.get('trade_diagnostic', False) and not closure.get('diplomacy_overview_diagnostic', False):
            raise ValueError('Trade cannot fall back to another session profile')
        if closure.get('world_congress_diagnostic', False) and not (
                closure.get('espionage_diagnostic', False) or
                closure.get('stock_dedications', False) and closure.get('world_congress_review_diagnostic', False)):
            raise ValueError('Congress requires the complete XP2 BBG or stock review chain')
        if closure.get('world_congress_review_diagnostic', False) and closure.get('world_congress_diagnostic') is not True:
            raise ValueError('Congress review requires the explicit Congress chain')
        if closure.get('trade_overview_ui_selected', False) and (
                closure['input_profile'] != 'xp2-lan' or closure.get('world_congress_review_diagnostic') is not True):
            raise ValueError('Trade overview requires the explicit current XP2 public query chain')
        if closure.get('espionage_diagnostic', False) and not closure.get('trade_diagnostic', False):
            raise ValueError('Espionage cannot fall back to another session profile')
        if not xp1:
            from civ6_host.runtime.captured_saved_load import validate_closure_profile
            validate_closure_profile(closure)
        display_formatter = None
        if 'public_display_source' in closure:
            from civ6_host.runtime.player_display_toppanel import (
                OwnedNativeTopPanelFormatter, require_display_closure)
            require_display_closure(closure)
        from civ6_host.runtime.workers.run_official_postload909 import open_official_backend
        from civ6_host.runtime.native.native_official_postload import observe_saved_player
        from civ6_host.runtime.native.native_episode_identity import require_episode
        from civ6_host.runtime.native.native_saved_session_protocol import outcome
        from civ6_host.runtime.native.native_victory_diagnostic import (
            observe_after_round_echo, NativeVictoryReached)
        from civ6_host.contracts.session_result import project_inactive_player
        from civ6_host.runtime import network_owner

        compare_initial = None
        if xp1:
            from civ6_host.runtime import xp1_session_view, xp1_session_result
            owner, compare_initial = _open_xp1(closure, path, emit, win)
            local_player = owner.network_reference['state']['player_id']
            protocol = NetworkProtocol(require_episode(owner.prefix), closure['nonce'],
                round_limit=closure['rounds'], initial_turn=closure['initial_turn'],
                core_sha256=owner.backend.load_abi.core_sha256,
                war_source_sha256=closure.get('war_source_sha256'))
            _emit_native_load_profile(owner, protocol, local_player, emit)
        else:
            owner = open_official_backend(closure, emit, win)
            initial = observe_saved_player(owner)
            session, compare_initial = network_owner.prepare(owner, initial)
            local_player = session['local_player_id']
            protocol = NetworkProtocol(require_episode(owner.prefix), closure['nonce'],
                round_limit=closure['rounds'], initial_turn=closure['initial_turn'])
            owner.explicit_initial_turn = initial['turn']
            owner.explicit_round_limit = protocol.limit
            for flag in ('forced_endturn_diagnostic', 'production_queue_diagnostic',
                         'multiturn_movement_diagnostic', 'movement_information_diagnostic',
                         'unit_order_cancel_diagnostic', 'world_input_diagnostic',
                         'city_focus_diagnostic', 'city_management_diagnostic'):
                value = closure.get(flag, False)
                if type(value) is not bool:
                    raise ValueError('Exact diagnostic option required: ' + flag)
                setattr(owner, flag, value)
            if owner.city_management_diagnostic and not owner.city_focus_diagnostic:
                raise ValueError('City management requires the complete focus group')

        if 'public_display_source' in closure:
            display_formatter = OwnedNativeTopPanelFormatter(owner, protocol,
                source_sha256=closure['public_display_source'])

        critic = None
        if closure.get('privileged_critic_diagnostic', False):
            from civ6_host.runtime.xp2_bbg_critic import CriticReadback
            critic = CriticReadback(closure, path)

        def reply(operation, player_id, sequence, command, request=None,
                  command_seconds=None, trace_before=None, borrowed=None):
            started = perf_counter()
            if borrowed is not None:
                native, session, observation, decisions, command = borrowed
                rounds = native['current_game_turn'] - protocol.initial_turn
            elif xp1:
                native = _read_xp1_outcome(owner, player_id)
                rounds = native['current_game_turn'] - protocol.initial_turn
            else:
                session = network_owner.state(owner)
                from civ6_host.runtime.network_dialogue import control
                control(owner)
                try:
                    native = observe_after_round_echo(owner.prefix, player_id, session['turn'])
                except NativeVictoryReached as exc:
                    native = exc.result
                rounds = session['turn'] - protocol.initial_turn
            result = outcome(native, rounds, protocol.limit,
                closed=operation == 'close', maximum=protocol.max_round_limit)
            inactive_player = project_inactive_player(result,
                episode_id=protocol.identity.episode_id, game_generation=protocol.identity.game_generation,
                player_id=player_id, turn=native['current_game_turn'])
            if native['episode_terminated'] or inactive_player is not None:
                observation, decisions = None, None
                if xp1 and borrowed is None:
                    inactive_actor = player_id if native.get('is_alive') is False else None
                    session = xp1_session_view.state(owner, inactive_player_id=inactive_actor)
            elif borrowed is not None:
                if result['truncated']:
                    raise RuntimeError('Borrowed actor reply crossed the already admitted round limit')
            elif xp1:
                session, observation, decisions = xp1_session_view.read(owner, player_id, sequence,
                    actions_closed=result['terminated'] or result['truncated'],
                    specialist_diagnostic=operation!='close')
            else:
                observation, decisions = network_owner.read(owner, sequence, rounds,
                    closed=result['terminated'] or result['truncated'],
                    round_limit=protocol.limit, player_id=player_id)
            view_seconds = perf_counter() - started
            started = perf_counter()
            response = dict(stage='official_session_response', schema=SCHEMA,
                nonce=protocol.nonce, episode_id=protocol.identity.episode_id,
                game_generation=protocol.identity.game_generation, sequence=sequence,
                operation=operation, observation=observation, rounds=rounds,
                outcome=result, decisions=decisions, command_result=command,
                session=session, applied_action=command['requested_action']
                    if command['status'] == 'completed' else None,
                automatic_choices_applied=False, action_interface_complete=False,
                strategic_training_ready=False)
            validate_network_response(response, protocol, operation, request=request)
            if operation == 'reset' and owner.inputs.checkpoint is not None:
                if compare_initial is None:
                    raise RuntimeError('Missing checkpoint comparator for restored decision boundary')
                compare_initial(observation, decisions)
            if operation == 'reset' and closure['input_profile'] == 'xp2-lan' and observation is not None:
                from civ6_host.runtime.xp2_end_turn_readback import SOURCE, read
                end_turn = read(owner, player_id, session['turn'])
                emit('xp2_saved_end_turn_observed', episode_id=protocol.identity.episode_id,
                     game_generation=protocol.identity.game_generation, sequence=sequence,
                     player_id=player_id, turn=session['turn'], end_turn=end_turn,
                     source_sha256=SOURCE[1], actor_channel=False)
            if borrowed is None and display_formatter is not None and observation is not None and not result['terminated']:
                from civ6_host.runtime.player_display_toppanel import emit_display_readback
                emit_display_readback(display_formatter, owner, response, request, emit)
            if borrowed is None and critic is not None and observation is not None and not (result['terminated'] or result['truncated']):
                critic.emit_ready(owner, response, emit)
            if borrowed is None and foundation_legality is not None and observation is not None and not (result['terminated'] or result['truncated']):
                foundation_legality(owner, response, emit)
            if operation == 'close' and xp1:
                from civ6_host.runtime.xp1_session_inputs import _write_once
                emit('before_xp1_saved_loaded_close', completed_phase='unit_commands',
                     public_runtime_admitted=False)
                closed = owner.close()
                emit('xp1_saved_loaded_close_returned',
                    receipt=_write_once(_Path(path).resolve().parent/'loaded-lifetime-result.json', closed))
                # Reply describes the final state read before Destroy. No native
                # reader is called after it, and no success precedes teardown.
            if request is not None:
                protocol.commit_reply(request, response)
            protocol.accept_response(response)
            if lan_view_players and observation is not None and not (result['terminated'] or result['truncated']):
                publish_player_views(emit, owner, protocol, observation, closure, path,
                                     lan_players=lan_view_players)
            payload = json.dumps(response)
            if xp1 and operation == 'reset':
                emit('native_reset_timing', phase='saved_initial_response_seconds',
                     elapsed_seconds=view_seconds + (perf_counter() - started),
                     timing_scope='non-overlapping stage; includes observation and checkpoint comparison')
            if command_seconds is not None:
                records_before, seconds_before = trace_before
                emit('native_lan_response_timing', operation=operation, sequence=sequence,
                     command_seconds=command_seconds, view_seconds=view_seconds,
                     response_seconds=perf_counter() - started,
                     worker_trace_records=trace_records - records_before,
                     worker_trace_emit_seconds=trace_seconds - seconds_before,
                     worker_trace_emit_included_in_stage_times=True)
            print(payload, flush=True)

        profiler = None
        if closure.get('command_profile_diagnostic', False):
            from civ6_host.runtime.command_profiling import CommandProfiler
            profiler = CommandProfiler(enabled=True, emit=emit,
                identity=dict(episode_id=protocol.identity.episode_id,
                              game_generation=protocol.identity.game_generation))
        none = dict(status='none', reason=None, requested_action=None)
        reply('reset', local_player, 0, none)
        # Private administrative spy fixture hook v2.
        # Restore/compare the untouched checkpoint first. No protocol action is
        # added: the next ordinary observe receives the new native revision.
        if 'private_spy_fixture' in closure:
            import hashlib as fixture_hashlib
            from civ6_host.runtime import private_spy_fixture
            fixture_spec = closure['private_spy_fixture']
            fixture_path = _Path(private_spy_fixture.__file__).resolve()
            fixture_sha = fixture_hashlib.sha256(fixture_path.read_bytes()).hexdigest()
            if (not xp1 or closure['input_profile'] != 'xp2-lan'
                    or fixture_spec['module'] != private_spy_fixture.__name__
                    or fixture_path != _Path(fixture_spec['module_file']).resolve()
                    or fixture_sha != fixture_spec['module_sha256']
                    or closure['pins'].get(str(fixture_path)) != fixture_sha):
                raise ValueError('Unpinned private spy fixture')
            private_spy_fixture.install_fixture(owner, closure, emit)
        compare_initial = None
        for _ in range(protocol.max_commands):
            line = sys.stdin.buffer.readline(4097)
            if not line or len(line) > 4096 or not line.endswith(b'\n'):
                raise ValueError('Missing or oversized LAN command')
            request = json.loads(line)
            operation = protocol.validate(request)
            pid = request['player_id']
            command = none
            borrowed = None
            trace_before = trace_records, trace_seconds
            started = perf_counter()
            with (profiler.measure('command', operation, request['sequence'], pid)
                  if profiler is not None else nullcontext()):
                if pid != local_player:
                    if secondary_reader is None:
                        raise ValueError('The captured LAN worker only routes the local seat')
                    borrowed = secondary_reader(owner, protocol, request, lan_view_players)
                elif operation == 'act':
                    if xp1:
                        command = _execute_xp1(owner, protocol.selected(request), pid,
                                              protocol.sequence, path)
                    else:
                        command = network_owner.execute(owner, protocol.selected(request),
                            player_id=pid, sequence=protocol.sequence,
                            rounds=protocol.rounds, round_limit=protocol.limit)
                elif operation == 'poll':
                    if xp1:
                        _poll_xp1(owner,protocol.sequence,path)
                    else:
                        from civ6_host.runtime.network_turns import advance
                        advance(owner)
                elif operation == 'close' and closure.get('checkpoint_on_close', False):
                    _save_before_close(owner, protocol, closure, path, request, xp1, emit)
            command_seconds = perf_counter() - started
            with (profiler.measure('response', operation, request['sequence'], pid)
                  if profiler is not None else nullcontext()):
                reply(operation, pid, request['sequence'], command, request,
                      command_seconds=command_seconds if operation in ('act', 'poll') else None,
                      trace_before=trace_before, borrowed=borrowed)
            if operation == 'close':
                emit('official_session_controlled_stop', normal_destroy_called=xp1,
                     strategic_training_ready=False)
                terminate_worker(90)
        raise ValueError('Bounded LAN command budget exhausted')
    except BaseException as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit('official_session_refused', error=repr(exc), cleanup_guessed=False,
             strategic_training_ready=False)
        terminate_worker(89)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Expected private closure path')
    raise SystemExit(main(sys.argv[1]))
