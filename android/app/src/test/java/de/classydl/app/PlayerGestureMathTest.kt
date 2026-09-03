package de.classydl.app

import org.junit.Assert.assertEquals
import org.junit.Test

class PlayerGestureMathTest {
    @Test fun lowPercentagesMapToExactPlayerGainValues() {
        assertEquals(0.01f, PlayerGestureMath.unitValueFromPercent(1, 0), 0.000001f)
        assertEquals(0.02f, PlayerGestureMath.unitValueFromPercent(2, 0), 0.000001f)
        assertEquals(0.07f, PlayerGestureMath.unitValueFromPercent(7, 0), 0.000001f)
        assertEquals(1, PlayerGestureMath.percentFromUnitValue(0.01f))
        assertEquals(7, PlayerGestureMath.percentFromUnitValue(0.07f))
    }

    @Test fun slowDragAccumulatesIntoOnePercentSteps() {
        assertEquals(3, PlayerGestureMath.percentFromVerticalDrag(3, 1_000f, 1_009f, 2_000, 0))
        assertEquals(2, PlayerGestureMath.percentFromVerticalDrag(3, 1_000f, 1_011f, 2_000, 0))
        assertEquals(1, PlayerGestureMath.percentFromVerticalDrag(3, 1_000f, 1_040f, 2_000, 0))
    }

    @Test fun upwardDragRaisesVolumeByExactPercentagePoints() {
        assertEquals(4, PlayerGestureMath.percentFromVerticalDrag(3, 1_000f, 980f, 2_000, 0))
        assertEquals(7, PlayerGestureMath.percentFromVerticalDrag(3, 1_000f, 920f, 2_000, 0))
    }

    @Test fun volumeAndBrightnessUseTheirOwnSafeMinimums() {
        assertEquals(0, PlayerGestureMath.percentFromVerticalDrag(2, 1_000f, 2_000f, 2_000, 0))
        assertEquals(1, PlayerGestureMath.percentFromVerticalDrag(2, 1_000f, 2_000f, 2_000, 1))
        assertEquals(100, PlayerGestureMath.percentFromVerticalDrag(99, 1_000f, 0f, 2_000, 0))
    }
}
