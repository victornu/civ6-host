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
