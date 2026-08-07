package de.classydl.app

import android.content.Context

object InstallReferrerRepositoryFactory {
    fun create(context: Context, entitlementApi: EntitlementApi): InstallReferrerRepository =
        PlayInstallReferrerRepository(context, entitlementApi)
}
