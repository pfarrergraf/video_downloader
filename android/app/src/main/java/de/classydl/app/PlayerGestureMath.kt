package de.classydl.app

import kotlin.math.roundToInt

/** Pure gesture math kept Android-free so percentage behavior is unit-testable. */
internal object PlayerGestureMath {
    fun percentFromUnitValue(value: Float): Int =
        (value * 100f).roundToInt().coerceIn(0, 100)

    fun unitValueFromPercent(percent: Int, minPercent: Int): Float =
        percent.coerceIn(minPercent.coerceIn(0, 100), 100) / 100f

    fun percentFromVerticalDrag(
        startPercent: Int,
        startY: Float,
        currentY: Float,
        height: Int,
        minPercent: Int,
    ): Int {
        val safeMinimum = minPercent.coerceIn(0, 100)
        val safeStart = startPercent.coerceIn(safeMinimum, 100)
        if (height <= 0) return safeStart

        val percentagePoints = ((startY - currentY) * 100f / height).roundToInt()
        return (safeStart + percentagePoints).coerceIn(safeMinimum, 100)
    }
}
