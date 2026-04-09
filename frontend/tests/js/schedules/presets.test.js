import { fireEvent } from '@testing-library/dom';
import { getPreset } from '@schedules/presets.js';
import { attachPresetHandlers } from '@schedules/main.js';

import fixtureHTML from '../fixtures/schedules.html?raw';

describe('Schedule presets', () => {
  beforeEach(() => {
    document.body.innerHTML = fixtureHTML;
  });

  it('opens modal with lunch preset', () => {
    const button = document.querySelector('[data-preset="lunch"]');
    attachPresetHandlers();
    fireEvent.click(button);

    expect(document.getElementById('start-time').value).toBe(getPreset('lunch').start_time);
    expect(document.getElementById('end-time').value).toBe(getPreset('lunch').end_time);
  });

  it('opens modal with dinner preset', () => {
    const button = document.querySelector('[data-preset="dinner"]');
    attachPresetHandlers();
    fireEvent.click(button);

    expect(document.getElementById('start-time').value).toBe(getPreset('dinner').start_time);
    expect(document.getElementById('end-time').value).toBe(getPreset('dinner').end_time);
  });

  it('allows overriding preset values', () => {
    const button = document.querySelector('[data-preset="lunch"]');
    attachPresetHandlers();
    fireEvent.click(button);

    const startInput = document.getElementById('start-time');
    fireEvent.change(startInput, { target: { value: '11:00' } });
    expect(startInput.value).toBe('11:00');
  });
});
