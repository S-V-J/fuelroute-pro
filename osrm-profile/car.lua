-- OSRM car profile for FuelRoute Pro
-- Based on standard OSRM car profile with minor adjustments for US routing

api_version = 4

Set = require('lib/set')
Sequence = require('lib/sequence')
Handlers = require('lib/way_handlers')
Relations = require('lib/relations')
find_access_tag = require('lib/access').find_access_tag
limit = require('lib/maxspeed').limit

function setup()
  return {
    properties = {
      max_speed_for_map_matching = 180/3.6, -- 180kmh -> m/s
      weight_name = 'routability',
      -- For route calculation we only consider motorized vehicles
      exclude_tags = {
        motorway = true,
        trunk = true,
        primary = true,
        secondary = true,
        tertiary = true,
        unclassified = true,
        residential = true,
        service = true,
        living_street = true,
        road = true,
        track = true,
        path = true,
        cycleway = true,
        pedestrian = true,
        footway = true,
        steps = true,
        bridleway = true,
      }
    },

    default_mode = mode.driving,
    default_speed = 50,
    oneway_handling = true,
    side_road_multiplier = 0.8,
    turn_penalty = 7.5,
    speed_reduction = 0.8,
    -- OSRM uses km/h internally
    -- maxspeed=50 means 50 km/h

    -- Vehicle dimensions for weight restrictions
    vehicle_height = 4.0, -- meters
    vehicle_width = 2.6,  -- meters
    vehicle_length = 18.75, -- meters (US semi-truck)
    vehicle_weight = 36000, -- kg (80,000 lbs GVW)
    vehicle_axle_load = 10000, -- kg per axle

    -- Classifications for road types
    classifications = {
      {name = 'motorway', classes = Set{'motorway', 'motorway_link'}},
      {name = 'trunk', classes = Set{'trunk', 'trunk_link'}},
      {name = 'primary', classes = Set{'primary', 'primary_link'}},
      {name = 'secondary', classes = Set{'secondary', 'secondary_link'}},
      {name = 'tertiary', classes = Set{'tertiary', 'tertiary_link'}},
      {name = 'unclassified', classes = Set{'unclassified', 'road'}},
      {name = 'residential', classes = Set{'residential', 'living_street'}},
      {name = 'service', classes = Set{'service', 'track', 'path'}},
      {name = 'ferry', classes = Set{'ferry'}},
      {name = 'cycleway', classes = Set{'cycleway'}},
      {name = 'pedestrian', classes = Set{'pedestrian', 'footway', 'steps', 'bridleway'}},
    },

    speeds = {
      motorway = 120,
      motorway_link = 80,
      trunk = 100,
      trunk_link = 70,
      primary = 90,
      primary_link = 60,
      secondary = 80,
      secondary_link = 50,
      tertiary = 70,
      tertiary_link = 40,
      unclassified = 60,
      residential = 50,
      service = 30,
      track = 20,
      path = 15,
      cycleway = 15,
      pedestrian = 5,
      ferry = 5,
      default = 50,
    },

    service_penalties = {
      alley = 0.5,
      parking = 0.5,
      parking_aisle = 0.5,
      driveway = 0.5,
      ['drive-through'] = 0.5,
    },

    access_tag_whitelist = Set{
      'yes',
      'motor_vehicle',
      'vehicle',
      'permissive',
      'designated',
      'destination',
    },

    access_tag_blacklist = Set{
      'no',
      'agricultural',
      'forestry',
      'private',
      'delivery',
    },

    restricted_access_tag_list = Set{},
    restricted_highway_whitelist = Set{},

    -- Access restrictions
    construction = {'construction', 'proposed'},
    -- Don't route through areas under construction
    ignore_construction = false,
  }
end

function process_node(profile, node, result)
  -- Node processing for traffic signals, crossings, etc.
  if node:get_value_by_key("highway") == "traffic_signals" then
    result.traffic_lights = true
  end
end

function process_way(profile, way, result)
  -- Initial filtering
  local highway = way:get_value_by_key('highway')
  if not highway then
    return
  end

  -- Check if way is routable
  local classification = profile.classifications[highway]
  if not classification then
    return
  end

  -- Access restrictions
  local access = find_access_tag(way, profile.access_tag_whitelist, profile.access_tag_blacklist)
  if access == 'no' then
    return
  end

  -- One-way handling
  local oneway = way:get_value_by_key('oneway')
  if oneway == 'yes' or oneway == '1' or oneway == 'true' then
    result.forward_mode = mode.driving
    result.backward_mode = mode.inaccessible
  elseif oneway == '-1' then
    result.forward_mode = mode.inaccessible
    result.backward_mode = mode.driving
  else
    result.forward_mode = mode.driving
    result.backward_mode = mode.driving
  end

  -- Speed handling
  local maxspeed = limit(way, profile.default_speed, profile.speeds)
  if maxspeed then
    result.forward_speed = maxspeed
    result.backward_speed = maxspeed
  else
    result.forward_speed = profile.speeds[highway] or profile.default_speed
    result.backward_speed = profile.speeds[highway] or profile.default_speed
  end

  -- Service roads penalty
  local service = way:get_value_by_key('service')
  if service and profile.service_penalties[service] then
    result.forward_speed = result.forward_speed * profile.service_penalties[service]
    result.backward_speed = result.backward_speed * profile.service_penalties[service]
  end

  -- Turn restrictions
  if way:get_value_by_key('junction') == 'roundabout' then
    result.roundabout = true
  end

  -- Weight calculation for routing
  result.weight = result.forward_speed / 3.6 -- convert km/h to m/s

  -- Name for instructions
  local name = way:get_value_by_key('name')
  local ref = way:get_value_by_key('ref')
  if name and ref then
    result.name = name .. ' (' .. ref .. ')'
  elseif name then
    result.name = name
  elseif ref then
    result.name = ref
  end
end

function process_turn(profile, turn)
  -- Turn penalties
  if turn.has_traffic_light then
    turn.duration = turn.duration + profile.turn_penalty
  end
  if turn.is_u_turn then
    turn.duration = turn.duration + profile.turn_penalty * 2
  end
end

return {
  setup = setup,
  process_way = process_way,
  process_node = process_node,
  process_turn = process_turn,
}