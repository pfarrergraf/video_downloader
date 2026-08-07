package de.classydl.app

/** Small flavor-neutral lifecycle contract for optional Play Install Referrer collection. */
interface InstallReferrerRepository {
    fun start()
    fun close()
}
