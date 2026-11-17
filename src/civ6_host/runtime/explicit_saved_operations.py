"""Reuse explicit UI unit operations without constructing a NewGame prefix.

NativeMapScriptPrefix keeps the one implementation. This facade requires the
selected identifiers, so its old diagnostic auto-selection branches are unused.
Other families are joined only with their own engine-qualified dependencies.
"""
from .native.native_map_script import NativeMapScriptPrefix

class ExplicitSavedOperations:
    @property
    def operation_core_sha256(self):
        return self.backend.load_abi.core_sha256

    def inspect_own_religion_snapshot(self, player_id):
        from .xp1_religion_observation_source import bind_prefix
        from .native.native_religion_observation import inspect_snapshot
        bind_prefix(self)
        return inspect_snapshot(self, player_id, core_sha256=self.operation_core_sha256)

    def inspect_prophet_activation_choice(self, player_id, *, selected_unit_id,
            expected_x, expected_y, expected_type_index, expected_turn):
        from .xp1_prophet_activation_source import bind_prefix
        from .native.native_religion_diagnostic import activate_prophet
        from .native.native_prophet_activation import _validate_choice, OPERATION_HASH
        choice = dict(player_id=player_id, current_game_turn=expected_turn,
            unit_id=selected_unit_id, x=expected_x, y=expected_y,
            prophet_type_index=expected_type_index, operation=OPERATION_HASH)
        _validate_choice(choice)
        bind_prefix(self, action=True)
        return activate_prophet(self, player_id, selected_unit_id=selected_unit_id,
            expected_choice=choice, core_sha256=self.operation_core_sha256)

    def inspect_religion_founding_choice(self, player_id, *, selected_index, selected_hash):
        from .xp1_religion_founding_source import bind_prefix
        from .native.native_religion_diagnostic import found_religion
        from .native.native_religion_founding import _uint
        _uint(selected_index, 'selected religion index', 0x7fffffff)
        _uint(selected_hash, 'selected religion hash')
        bind_prefix(self, action=True)
        return found_religion(self, player_id, selected_index=selected_index,
            expected_hash=selected_hash, core_sha256=self.operation_core_sha256,
            read=self.backend.runtime.read)

    def inspect_religion_belief_choice(self, player_id, *, selected_index, selected_hash, selected_class):
        from .xp1_religion_beliefs_source import bind_prefix
        from .native.native_religion_diagnostic import add_belief
        from .native.native_religion_beliefs import _uint, _class
        if type(selected_index) is not int or not 0 <= selected_index <= 0x7fffffff:
            raise ValueError('An explicit religious belief index is required')
        _uint(selected_hash, 'selected belief hash')
        _class(selected_class)
        bind_prefix(self, action=True)
        return add_belief(self, player_id, selected_index=selected_index,
            expected_hash=selected_hash, expected_class=selected_class,
            core_sha256=self.operation_core_sha256, read=self.backend.runtime.read)

    def inspect_pantheon_choice(self, player_id, *, selected_index):
        from .xp1_pantheon_source import bind_prefix
        from .native.native_saved_pantheon import inspect_choice
        if type(selected_index) is not int or not 0 <= selected_index <= 0x7fffffff:
            raise ValueError('An explicit pantheon belief index is required')
        bind_prefix(self, action=True)
        return inspect_choice(self, player_id, selected_index=selected_index,
            core_sha256=self.operation_core_sha256, read=self.backend.runtime.read)

    def inspect_player_research_choice(self, player_id, kind, *, selected_index):
        if type(selected_index) is not int or not 0 <= selected_index <= 0xffffffff:
            raise ValueError('An explicit research/civic choice is required')
        return NativeMapScriptPrefix.inspect_player_research_choice(
            self, player_id, kind, selected_index=selected_index, submit_preselected=True)

    def inspect_found_city(self,player_id,*,unit_id,expected_x,expected_y):
        if unit_id is None or expected_x is None or expected_y is None:
            raise ValueError('An explicit founder and coordinates are required')
        return NativeMapScriptPrefix.inspect_found_city(self,player_id,
            unit_id=unit_id,expected_x=expected_x,expected_y=expected_y)

    def inspect_unit_movement(self,player_id,*,unit_id,destination_plot_id,
                              allow_improvements=False,allow_own_cities=False,allow_multiturn=False):
        if unit_id is None or destination_plot_id is None:
            raise ValueError('An explicit unit and destination are required')
        return NativeMapScriptPrefix.inspect_unit_movement(self,player_id,
            unit_id=unit_id,destination_plot_id=destination_plot_id,require_candidate=True,
            resolve_friendly_blockage=False,allow_improvements=allow_improvements,
            allow_own_cities=allow_own_cities,allow_multiturn=allow_multiturn)
