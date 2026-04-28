import { APIConfig } from './api-client'

/**
 * DEPRECATED: File-based config loader
 * 
 * Settings are now loaded exclusively from Python backend via pythonBridge.settings.get()
 * This module is kept for backwards compatibility but returns null.
 */
export async function loadConfigFromFile(): Promise<null> {
  console.log('[DEPRECATED] loadConfigFromFile() - Settings now loaded from Python backend only')
  return null
}
