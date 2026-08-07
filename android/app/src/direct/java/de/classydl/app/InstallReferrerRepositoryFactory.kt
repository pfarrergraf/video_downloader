package de.classydl.app

import android.content.Context

object InstallReferrerRepositoryFactory {
    fun create(context: Context, entitlementApi: EntitlementApi): InstallReferrerRepository =
        object : InstallReferrerRepository {
            override fun start() = Unit
            override fun close() = Unit
        }
}
