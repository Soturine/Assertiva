package demo.notes;

import static org.junit.Assert.assertEquals;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class LaunchTest {
    @Test
    public void packageNameIsTheApplicationId() {
        assertEquals("demo.notes", InstrumentationRegistry.getInstrumentation().getTargetContext().getPackageName());
    }
}
