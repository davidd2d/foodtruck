import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import { buildRecommendedMessage, SlotSelector } from '../../../static/js/components/slotSelector.js';

const slotSelectorFixture = readFileSync(
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), './fixtures/slotSelector.html'),
  'utf-8',
);

describe('SlotSelector helper', () => {
  it('builds a next available pickup message for a future slot', () => {
    const future = new Date();
    future.setHours(future.getHours() + 2);
    const slot = {
      id: 123,
      start_time: future.toISOString(),
      end_time: new Date(future.getTime() + 30 * 60000).toISOString(),
      is_available: true,
    };

    expect(buildRecommendedMessage(slot)).toContain('Prochain créneau disponible');
  });

  it('builds an immediate pickup message when the slot is current', () => {
    const now = new Date();
    const slot = {
      id: 456,
      start_time: new Date(now.getTime() - 5 * 60000).toISOString(),
      end_time: new Date(now.getTime() + 25 * 60000).toISOString(),
      is_available: true,
    };

    expect(buildRecommendedMessage(slot)).toBe('Retrait conseillé : dès maintenant');
  });
});

describe('SlotSelector integration', () => {
  beforeEach(() => {
    document.body.innerHTML = slotSelectorFixture;
  });

  it('preselects the recommended slot and updates help text when defaultSlotId matches', () => {
    const selectElement = document.getElementById('pickup-slot-select');
    const helpElement = document.getElementById('pickup-slot-help');
    const onSelectionChange = vi.fn();

    const slotSelector = new SlotSelector({
      selectElement,
      helpElement,
      onSelectionChange,
    });

    const slots = [
      {
        id: 1,
        start_time: new Date(Date.now() + 60 * 60000).toISOString(),
        end_time: new Date(Date.now() + 90 * 60000).toISOString(),
        is_available: true,
      },
      {
        id: 2,
        start_time: new Date(Date.now() + 30 * 60000).toISOString(),
        end_time: new Date(Date.now() + 60 * 60000).toISOString(),
        is_available: true,
      },
      {
        id: 3,
        start_time: new Date(Date.now() - 60 * 60000).toISOString(),
        end_time: new Date(Date.now() - 30 * 60000).toISOString(),
        is_available: false,
      },
    ];

    slotSelector.populateOptions(slots);

    expect(selectElement.disabled).toBe(false);
    expect(selectElement.value).toBe('2');
    expect(helpElement.textContent).toContain('Prochain créneau disponible');
    expect(onSelectionChange).toHaveBeenCalledWith(2);
  });
});
