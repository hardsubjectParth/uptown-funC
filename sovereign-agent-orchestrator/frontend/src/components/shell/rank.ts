import type { Role } from '../../types/api'

// The rebuild spec only defines the admin mapping ("Commander Alpha" / "Sovereign Tier
// Access"). higher/lower are our own extension, kept in the same register.
export const RANK: Record<Role, { name: string; subtitle: string }> = {
  admin: { name: 'Commander Alpha', subtitle: 'Sovereign Tier Access' },
  higher: { name: 'Operator Beta', subtitle: 'Elevated Tier Access' },
  lower: { name: 'Field Agent', subtitle: 'Standard Tier Access' },
}
