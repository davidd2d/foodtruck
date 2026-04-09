export const PRESETS = {
    lunch: {
        start_time: '12:00',
        end_time: '14:00',
        capacity_per_slot: 6,
        slot_duration_minutes: 10,
        day: 0,
    },
    dinner: {
        start_time: '19:00',
        end_time: '22:00',
        capacity_per_slot: 8,
        slot_duration_minutes: 10,
        day: 0,
    },
};

export function getPreset(key) {
    return PRESETS[key] ?? null;
}
