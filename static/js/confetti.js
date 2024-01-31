var amount = 2000,
    between = (min, max) => min + Math.random() * (max - min),
    colors = [
        "#d400ff",
        "#067df7",
        "#ff0080",
        "#F3722C",
        "#F8961E",
        "#F9C74F",
        "#90BE6D",
        "#43AA8B",
        "#577590"
    ],
    current = 0;

let interval = setInterval(() => {
    if (current < amount) {
        animate(createConfetti());
    }
}, 50);

setTimeout(() => clearInterval(interval), 5000);

function createConfetti() {
    let div = document.createElement('div');
    // Randomize the size and shape of the confetti
    let size = between(10, 25); // Increase the minimum and maximum values
    let shape = Math.random() > 0.5 ? 'circle' : 'square';
    gsap.set(div, {
        attr: {
            class: 'confetti',
            style: '--color: ' + colors[Math.floor(Math.random() * colors.length)]
        },
        x: between(0, window.innerWidth),
        y: -window.innerHeight / 4,
        z: between(-80, 80),
        width: size,
        height: size,
        borderRadius: shape === 'circle' ? '50%' : '0%'
    });
    current++;
    document.body.appendChild(div);
    return div;
}

function animate(element) {
    // Adjust the gravity, drag, and terminal velocity values
    let gravity = 0.3;
    let drag = 0.05;
    let terminalVelocity = 10;
    // Randomize the initial velocity and rotation of the confetti
    let velocityX = between(-25, 25);
    let velocityY = between(0, -50);
    let rotationX = between(0, 360);
    let rotationY = between(0, 360);
    let rotationZ = between(0, 360);
    gsap.to(element, {
        y: window.innerHeight + 40,
        ease: 'power1.out',
        delay: between(0, .25),
        duration: between(2, 5),
        onComplete() {
            if (element instanceof Element || element instanceof HTMLDocument) {
                current--;
                element.remove();
            }
        }
    });
    gsap.to(element, {
        rotationZ: rotationZ + between(90, 180),
        repeat: -1,
        yoyo: true,
        duration: between(3, 6)
    });
    gsap.to(element, {
        rotationX: rotationX + between(0, 360),
        rotationY: rotationY + between(0, 360),
        repeat: -1,
        yoyo: true,
        duration: between(3, 6)
    });
    // Apply forces to velocity and position
    gsap.ticker.add(() => {
        velocityX -= velocityX * drag;
        velocityY = Math.min(velocityY + gravity, terminalVelocity);
        velocityX += Math.random() > 0.5 ? Math.random() : -Math.random();
        velocityY += Math.random() > 0.5 ? Math.random() : -Math.random();
        element._gsTransform.x += velocityX;
        element._gsTransform.y += velocityY;
    });
    // Increase the scale factor of each particle
    gsap.to(element, {
        scale: 1.5, // Change this value to make the confetti bigger or smaller
        ease: "elastic.out(1, 0.3)",
        duration: 1
    });
}
