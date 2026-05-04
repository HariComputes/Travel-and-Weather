/*const now = new Date();
const hour = now.getHours();
if (hour >= 6 && hour < 10) {
    setTimeout(() => location.reload(), 300000); // 5 minutes
}
*/

function scheduleRefresh() {
    const now = new Date();
    const hour = now.getHours();

    if (hour >= 6 && hour < 10) {
        setTimeout(() => {
            location.reload();
        }, 600000); // 10 minutes
    } else {
        // Check again in 10 minutes to see if we're in the window
        setTimeout(scheduleRefresh, 600000);
    }
}

// Start the loop
scheduleRefresh();

