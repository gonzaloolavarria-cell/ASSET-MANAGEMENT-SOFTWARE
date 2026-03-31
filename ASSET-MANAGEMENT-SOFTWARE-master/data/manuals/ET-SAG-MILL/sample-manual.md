# SAG Mill — Operations & Maintenance Manual

## 1. General Description

The Semi-Autogenous Grinding (SAG) Mill is a primary grinding unit used in phosphate ore processing. It reduces run-of-mine (ROM) ore from ~150mm to ~1-2mm using a combination of ore self-grinding and steel ball charge (8-15% ball charge by volume).

### 1.1 Key Specifications

| Parameter | Value |
|-----------|-------|
| Mill diameter | 9.75 m (32 ft) |
| Mill length | 5.18 m (17 ft) |
| Power rating | 8,500 kW |
| Speed range | 9.0 - 11.5 RPM (65-78% critical speed) |
| Ball charge | 8-15% by volume |
| Feed size | F80 = 150 mm |
| Product size | P80 = 1.5 mm |
| Weight (empty) | 450,000 kg |
| Liner material | High-chrome white iron (Cr-Mo alloy) |
| Expected life | 30 years |

### 1.2 Main Components

- **Shell**: Welded steel cylinder with flanged heads
- **Trunnions**: Forged alloy steel, supported on hydrodynamic bearings
- **Liners**: Lifter bars + shell plates (high-chrome, 6-12 month replacement cycle)
- **Grate/Pulp lifters**: Control product discharge size
- **Drive system**: Ring gear + pinion, with main motor (8,500 kW synchronous)
- **Lubrication system**: High-pressure oil film bearings (HSB), centralized grease

## 2. Operating Procedures

### 2.1 Startup Sequence

1. **Pre-start checks** (30 minutes before):
   - Verify lubrication system pressures: HSB oil pressure > 2.5 MPa
   - Confirm cooling water flow to bearings and motor
   - Check inching drive engagement (disengaged)
   - Inspect feed chute and discharge screen for blockages
   - Verify all guards and safety interlocks are in place

2. **Slow roll** (inching drive):
   - Engage inching drive for 2 full revolutions
   - Listen for abnormal sounds (metallic banging = loose liner)
   - Check for ore buildup or frozen charge

3. **Main drive start**:
   - Start lubrication system (oil and grease)
   - Wait 60s for oil film to establish
   - Start main motor (ramp to operating speed over 30s)
   - Verify current draw < 110% rated during startup
   - Begin feed at 50% design rate, increase over 15 minutes

### 2.2 Normal Operation

- **Feed rate**: 1,200-1,800 t/h (adjust based on bearing pressure and power draw)
- **Mill power draw**: Target 7,200-8,200 kW (85-96% rated)
- **Bearing temperature**: < 65°C (alarm at 70°C, trip at 80°C)
- **Mill sound**: Steady roar; cascading pattern audible. Sudden quiet = overloaded
- **Discharge density**: 65-75% solids by weight

### 2.3 Shutdown Sequence

1. Stop ore feed; continue water feed for 5 minutes (flush)
2. Run mill empty for 10 minutes to clear charge
3. Stop main motor
4. Engage barring device within 30 minutes (prevent thermal bowing)
5. Continue lubrication for 30 minutes after stop

## 3. Maintenance Procedures

### 3.1 Liner Inspection and Replacement

**Frequency**: Visual inspection every 2 weeks; replacement every 6-12 months

**Procedure**:
1. Lock out / tag out (LOTO) all energy sources
2. Enter mill through manhole (confined space permit required)
3. Measure liner thickness at 12 positions (minimum 25mm wear limit)
4. Replace liners below 30mm thickness (preventive threshold)
5. Torque liner bolts to 800 Nm (dry) in star pattern
6. Record liner thickness in maintenance log

**Critical safety**: Never enter mill without confirming electrical isolation AND mechanical barring device engaged.

### 3.2 Trunnion Bearing Maintenance

**Frequency**: Oil analysis monthly; major inspection annually

**Oil analysis targets**:
- Viscosity: ISO VG 320 (±10%)
- Water content: < 200 ppm (alarm at 500 ppm)
- Particle count: ISO 18/16/13 or cleaner
- Iron content: < 50 ppm (trending upward = bearing wear)

**Annual inspection**:
1. Drain and flush oil system
2. Inspect babbitt surface for scoring, pitting, or fatigue cracks
3. Measure bearing clearance (design: 0.15-0.25mm per side)
4. Check oil cooler effectiveness (oil temp delta < 15°C)

### 3.3 Drive System Maintenance

**Girth gear and pinion**:
- Check tooth contact pattern quarterly (60-80% face width contact)
- Grease spray system: verify nozzle alignment and flow rate weekly
- Backlash measurement: 1.5-2.5mm (adjust if outside range)
- Pinion bearing vibration: < 4.5 mm/s RMS velocity

**Motor**:
- Insulation resistance test: every 6 months (>100 MΩ at 40°C)
- Bearing vibration: < 3.5 mm/s RMS (alarm at 5.0, trip at 7.5)
- Air gap measurement: annual (uniform ±10%)
- Stator temperature: < 120°C (Class F insulation)

### 3.4 Grate and Pulp Lifter Maintenance

**Frequency**: Inspect at every liner change

- Check grate slot width (design: 12mm, replace at 20mm)
- Inspect pulp lifters for wear and blockage
- Clean slots of packed material (pebble port plugging)
- Check rubber seal between grate and shell

## 4. Troubleshooting Guide

### 4.1 High Bearing Temperature

| Possible Cause | Check | Action |
|----------------|-------|--------|
| Low oil flow | Oil flow meter | Clean filter, check pump |
| Oil cooler fouled | Water outlet temperature | Clean cooler tubes |
| Bearing overloaded | Mill charge level | Reduce feed rate |
| Oil degradation | Oil analysis results | Replace oil if viscosity out of range |
| Misalignment | Bearing pad temperatures | Realign mill if differential >5°C |

### 4.2 Abnormal Vibration

| Possible Cause | Check | Action |
|----------------|-------|--------|
| Uneven charge | Power draw fluctuation | Adjust ball charge |
| Loose liner bolt | Visual + audio (rattling) | Retorque or replace bolt |
| Foundation settling | Level measurements | Shim and realign |
| Pinion wear | Gear mesh vibration spectrum | Replace pinion set |
| Motor bearing failure | Motor vibration spectrum | Replace bearing |

### 4.3 Low Throughput

| Possible Cause | Check | Action |
|----------------|-------|--------|
| Ball charge too low | Power draw (low) | Add balls to target 12% |
| Grate plugging | Discharge flow rate | Clean grate slots |
| Feed too coarse | Feed size distribution | Adjust crusher CSS |
| Mill overloaded | Power draw (high) + sound | Reduce feed rate |
| Liner wear | Internal inspection | Replace liners |

### 4.4 High Motor Current

| Possible Cause | Check | Action |
|----------------|-------|--------|
| Mill overcharged | Bearing pressure + sound | Stop feed until current normalizes |
| Ball charge too high | Calculate ball volume | Remove excess balls at next stop |
| Ore specific gravity change | Feed assay | Adjust feed rate for density |
| Electrical fault | Motor phase currents | Check for imbalance >3% |

## 5. Spare Parts — Critical

| Part | Quantity (Recommended) | Lead Time |
|------|----------------------|-----------|
| Liner set (shell + lifters) | 1 complete set | 16-20 weeks |
| Trunnion bearing (babbitt) | 1 spare half | 12-16 weeks |
| Pinion | 1 spare | 20-24 weeks |
| Girth gear segment | 2 segments | 24-32 weeks |
| Main motor bearing | 2 (DE + NDE) | 8-12 weeks |
| Grate panel set | 1 complete set | 12-16 weeks |
| HSB oil pump | 1 spare | 4-6 weeks |
| Oil cooler element | 1 spare | 6-8 weeks |
