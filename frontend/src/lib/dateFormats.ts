/** Wire/storage format (API params, localStorage, freeze-day keys) — must stay lexicographically sortable. */
export const API_DATE_FORMAT = 'YYYY-MM-DD';

/** User-facing date display format, everywhere a full date is shown (DatePicker/RangePicker fields). */
export const DISPLAY_DATE_FORMAT = 'DD.MM.YYYY';

/** Compact day/month display for grid column headers, where the year is implied by context. */
export const DISPLAY_DATE_SHORT_FORMAT = 'DD.MM';

/** Time-of-day format (TimePicker fields, assignment time_spent). */
export const TIME_FORMAT = 'HH:mm';
