import { describe, it, expect } from 'vitest';
import { interpolateAngle, interpolateFrames, type SimFrameRaw } from '../lib/interpolate';

describe('Interpolation Utility Functions', () => {
  it('correctly handles angular interpolation across 0/360 boundary', () => {
    // 350 deg to 10 deg -> shortest path is +20 deg
    const angleMid = interpolateAngle(350, 10, 0.5);
    expect(angleMid).toBeCloseTo(0, 1);

    // 10 deg to 350 deg -> shortest path is -20 deg
    const angleMidReverse = interpolateAngle(10, 350, 0.5);
    expect(angleMidReverse).toBeCloseTo(0, 1);

    // 0 deg to 90 deg at 50%
    expect(interpolateAngle(0, 90, 0.5)).toBeCloseTo(45, 1);
  });

  it('interpolates drone positions between frames', () => {
    const frames: SimFrameRaw[] = [
      {
        t: 0.0,
        drones: [
          {
            id: 1,
            lat: 18.52,
            lon: 73.85,
            alt: 20.0,
            heading: 0,
            battery_pct: 100.0,
            state: 'SURVEY',
          },
        ],
      },
      {
        t: 10.0,
        drones: [
          {
            id: 1,
            lat: 18.53,
            lon: 73.86,
            alt: 20.0,
            heading: 90,
            battery_pct: 90.0,
            state: 'SURVEY',
          },
        ],
      },
    ];

    // At t = 5.0 (midway)
    const midDrones = interpolateFrames(frames, 5.0);
    expect(midDrones).toHaveLength(1);
    expect(midDrones[0].lat).toBeCloseTo(18.525, 4);
    expect(midDrones[0].lon).toBeCloseTo(73.855, 4);
    expect(midDrones[0].heading).toBeCloseTo(45, 1);
    expect(midDrones[0].battery_pct).toBe(95.0);

    // Boundary conditions
    const early = interpolateFrames(frames, -5.0);
    expect(early[0].lat).toBeCloseTo(18.52, 4);

    const late = interpolateFrames(frames, 15.0);
    expect(late[0].lat).toBeCloseTo(18.53, 4);
  });
});
