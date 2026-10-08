// The accepted R1-\d{3} format has 1,000 possible codes (000–999).
// The API stores one accepted claim per distributor/province, so neither a
// detail list nor its summary count can exceed this code space. This is not
// the number of active operators; the independent 32,000-byte guards still apply.
export const MAX_PROVINCIAL_DISTRIBUTORS = 1_000;
