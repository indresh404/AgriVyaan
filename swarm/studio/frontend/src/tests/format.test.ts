import { describe, it, expect } from 'vitest';
import { formatDuration, formatDistance, formatArea, formatGSD, formatEnergy, formatLatLon } from '../lib/format';

describe('Format Utility Functions', () => {
  it('formats durations correctly into mm:ss.s', () => {
    expect(formatDuration(0)).toBe('0:00.0');
    expect(formatDuration(65.4)).toBe('1:05.4');
    expect(formatDuration(125)).toBe('2:05.0');
  });

  it('formats distance in metres and kilometres', () => {
    expect(formatDistance(450)).toBe('450 m');
    expect(formatDistance(1250)).toBe('1.25 km');
  });

  it('formats area into m2, hectares, and acres', () => {
    const area = formatArea(10000);
    expect(area.m2).toBe('10,000 m²');
    expect(area.ha).toBe('1.00 Ha');
    expect(area.acres).toBe('2.47 Acres');
  });

  it('formats GSD and energy', () => {
    expect(formatGSD(3.754)).toBe('3.75 mm/px');
    expect(formatEnergy(15.42)).toBe('15.4 Wh');
  });

  it('formats coordinates into compass direction strings', () => {
    const coords = formatLatLon(18.52043, 73.85671);
    expect(coords).toContain('18.52043°N');
    expect(coords).toContain('73.85671°E');
  });
});
