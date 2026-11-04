"""Own-city growth as displayed by the official numeric overview panel."""
import math

SCHEMA='civ6-host.city-growth.v1'
TEXT_FIELDS=('FoodPerTurnNum','FoodConsumption','NetFoodPerTurn','GrowthLongLabel',
    'FoodNeededForGrowth','OccupationMultiplier','HappinessBonus','OtherGrowthBonuses',
    'HousingMultiplier','TurnsUntilBornLost','FoodSurplusDeficitLabel',
    'ModifiedGrowthFoodPerTurn','TotalFoodSurplus')


def validate(value, player_id, turn, *, observation=None):
    if (type(value) is not dict or set(value)!={'schema','player_id','turn','cities'}
            or value['schema']!=SCHEMA or type(value['player_id']) is not int or value['player_id']!=player_id
            or type(value['turn']) is not int or value['turn']!=turn
            or type(value['cities']) is not list or len(value['cities'])>4096):
        raise ValueError('Foreign or unbounded public city growth')
    seen={}
    for row in value['cities']:
        if (type(row) is not dict or set(row)!={'city_id','population','occupied','housing','amenities','amenities_needed','happiness','display','starving','growth_icon'}
                or type(row['city_id']) is not int or not 0<=row['city_id']<2**32
                or type(row['population']) is not int or not 1<=row['population']<2**31
                or type(row['occupied']) is not bool or type(row['starving']) is not bool
                or type(row['happiness']) is not int or not 0<=row['happiness']<2**31):
            raise ValueError('Invalid public city growth fields')
        for key in ('housing','amenities','amenities_needed'):
            if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or abs(row[key])>1e12:
                raise ValueError('Invalid public city growth amount')
        display=row['display']
        if type(display) is not dict or set(display)!=set(TEXT_FIELDS)|{'GrowthLongNum'}:
            raise ValueError('Incomplete public growth display')
        for key in TEXT_FIELDS:
            v=display[key]
            if type(v) is not str or len(v.encode('utf-8'))>4096 or '\x00' in v:
                raise ValueError('Invalid public growth text')
        if type(display['GrowthLongNum']) is not int or not 0<=display['GrowthLongNum']<2**31:
            raise ValueError('Invalid displayed growth countdown')
        icon=row['growth_icon']
        if (type(icon) is not dict or set(icon)!={'color','u','v'}
                or icon['color'] not in ('StatBadCSGlow','StatNormalCSGlow','StatGoodCSGlow')
                or type(icon['u']) is not int or icon['u']!=0
                or type(icon['v']) is not int or icon['v'] not in (0,100,150)):
            raise ValueError('Invalid public growth icon')
        if row['city_id'] in seen:raise ValueError('Duplicate growth city')
        seen[row['city_id']]=row
    if observation is not None:
        if observation['player_id']!=player_id or observation['turn']!=turn:
            raise ValueError('City growth observation identity differs')
        cities={c['id']:c for c in observation['cities']}
        if len(cities)!=len(observation['cities']) or set(seen)!=set(cities):
            raise ValueError('Growth state does not cover exactly own observed cities')
        for cid,c in cities.items():
            if c['owner']!=player_id or seen[cid]['population']!=c['population']:
                raise ValueError('Growth population/ownership differs from public city')
    return value
