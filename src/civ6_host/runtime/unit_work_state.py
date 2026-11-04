"""Read the same own-unit getters used by the retained native work adapter."""
from civ6_host.contracts.unit_work_state import PLOT_SCHEMA, SCHEMA, validate


def source(player_id, turn, *, include_plot=False):
    from .native.native_saved_unit_work import preamble
    chunk = b'''
local out={'unit-work-state-v1|'..n(pid)..'|'..n(turn)}
for _,u in ipairs(ownUnits()) do
 local p=visiblePlot(u:GetX(),u:GetY())
 local moves=u:GetMovesRemaining()
 assert(type(moves)=='number' and moves==moves and moves>=0 and moves<=2147483648,'unit work state moves')
 local row={'U',n(integer(u:GetID(),'unit',0,4294967295)),
  n(integer(p:GetIndex(),'plot',0,4294967295)),
  n(integer(u:GetBuildCharges(),'charges',0,4294967295)),string.format('%.17g',moves)}
 -- VISIBLE_PLOT_FIELDS
 out[#out+1]=table.concat(row,'|')
end
ready();return table.concat(out,'\\n')
'''
    if include_plot:
        chunk = chunk.replace(b'unit-work-state-v1', b'unit-work-state-v2').replace(
            b'-- VISIBLE_PLOT_FIELDS', b"""
 row[#row+1]=n(integer(p:GetImprovementType(),'improvement',-1,2147483647))
 row[#row+1]=bool(p:IsImprovementPillaged(),'improvement pillaged') and '1' or '0'
 row[#row+1]=n(integer(p:GetRouteType(),'route',-1,2147483647))
 row[#row+1]=bool(p:IsRoutePillaged(),'route pillaged') and '1' or '0'
""")
    return preamble(player_id, turn) + chunk


def parse(raw, player_id, turn, *, include_plot=False):
    if type(raw) is not bytes or len(raw)>512*1024:
        raise ValueError('Unbounded unit-work state')
    lines=raw.decode('ascii').splitlines()
    version = 2 if include_plot else 1
    if not lines or lines[0]!=f'unit-work-state-v{version}|{player_id}|{turn}' or len(lines)>4097:
        raise ValueError('Foreign unit-work state')
    rows=[]
    for line in lines[1:]:
        cells=line.split('|')
        if (len(cells) != (9 if include_plot else 5) or cells[0] != 'U'
                or any(not c.isdigit() or str(int(c)) != c for c in cells[1:4])):
            raise ValueError('Malformed unit-work state row')
        row = dict(unit_id=int(cells[1]), plot_id=int(cells[2]), charges=int(cells[3]), moves_token=cells[4])
        if include_plot:
            if cells[6] not in ('0', '1') or cells[8] not in ('0', '1'):
                raise ValueError('Malformed unit-work pillage state')
            row.update(improvement=int(cells[5]), improvement_pillaged=cells[6] == '1',
                       route=int(cells[7]), route_pillaged=cells[8] == '1')
        rows.append(row)
    return validate(dict(schema=PLOT_SCHEMA if include_plot else SCHEMA,
                         player_id=player_id, turn=turn, units=rows),
                    player_id, turn, include_plot=include_plot)


def observe(owner, observation, work_catalog, *, include_plot=False):
    pid,turn=observation['player_id'],observation['turn']
    p=owner.prefix
    result=parse(p.runtime.evaluate_text(p.ui_child,source(pid,turn,include_plot=include_plot),
        b'@public_own_unit_work_state',capacity=512*1024+1),pid,turn,include_plot=include_plot)
    return validate(result,pid,turn,observation=observation,work_catalog=work_catalog,
                    include_plot=include_plot)
