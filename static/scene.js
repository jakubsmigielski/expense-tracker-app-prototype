import * as THREE from 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.module.js';
import { EffectComposer } from 'https://cdn.skypack.dev/three@0.128.0/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://cdn.skypack.dev/three@0.128.0/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'https://cdn.skypack.dev/three@0.128.0/examples/jsm/postprocessing/UnrealBloomPass.js';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ canvas: document.querySelector('#bg-3d'), antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
camera.position.set(0, 0, 10);

scene.add(new THREE.AmbientLight(0xffffff, 0.3));
const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
directionalLight.position.set(5, 10, 7.5);
scene.add(directionalLight);
const pointLight = new THREE.PointLight(0xffffff, 0.5);
pointLight.position.set(-5, -5, 5);
scene.add(pointLight);

const particlesCount = 1200;
const particlesGeometry = new THREE.BufferGeometry();
const posArray = new Float32Array(particlesCount * 3);
const particlesData = [];
for (let i = 0; i < particlesCount; i++) {
    const x = (Math.random() - 0.5) * 30;
    const y = (Math.random() - 0.5) * 30;
    const z = (Math.random() - 0.5) * 30;
    posArray[i * 3] = x; posArray[i * 3 + 1] = y; posArray[i * 3 + 2] = z;
    particlesData.push({ originalPos: new THREE.Vector3(x, y, z), velocity: new THREE.Vector3(0, 0, 0) });
}
particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
const textureLoader = new THREE.TextureLoader();
const dollarSVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="28px" font-weight="bold" fill="white">$</text></svg>`;
const encodedSVG = window.btoa(dollarSVG);
const dollarTexture = textureLoader.load('data:image/svg+xml;base64,' + encodedSVG);
const particlesMaterial = new THREE.PointsMaterial({ size: 0.5, map: dollarTexture, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending });
const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
scene.add(particlesMesh);

const logoGroup = new THREE.Group();
const material = new THREE.MeshStandardMaterial({ color: 0xeeeeee, metalness: 0.9, roughness: 0.1, emissive: 0x222222 });
const e_main = new THREE.Mesh(new THREE.BoxGeometry(0.5, 3, 0.5), material); e_main.position.x = -2;
const e_top = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.5, 0.5), material); e_top.position.set(-1.25, 1.25, 0);
const e_mid = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.5, 0.5), material); e_mid.position.set(-1.375, 0, 0);
const e_bot = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.5, 0.5), material); e_bot.position.set(-1.25, -1.25, 0);
logoGroup.add(e_main, e_top, e_mid, e_bot);
const t_main = new THREE.Mesh(new THREE.BoxGeometry(0.5, 3, 0.5), material); t_main.position.x = 1.75;
const t_top = new THREE.Mesh(new THREE.BoxGeometry(2, 0.5, 0.5), material); t_top.position.set(1.75, 1.25, 0);
logoGroup.add(t_main, t_top);
scene.add(logoGroup);

const renderScene = new RenderPass(scene, camera);
const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.85);
bloomPass.threshold = 0; bloomPass.strength = 1.2; bloomPass.radius = 0.5;
const composer = new EffectComposer(renderer);
composer.addPass(renderScene);
composer.addPass(bloomPass);

const mouse = new THREE.Vector2();
document.addEventListener('mousemove', (event) => { mouse.x = (event.clientX / window.innerWidth) * 2 - 1; mouse.y = -(event.clientY / window.innerHeight) * 2 + 1; });

const clock = new THREE.Clock();
const repelRadius = 7;
const repelStrength = 0.8;
const returnStrength = 0.010;
const damping = 0.5;

function animate() {
    const elapsedTime = clock.getElapsedTime();
    const positions = particlesGeometry.attributes.position.array;
    const mouse3D = new THREE.Vector3(mouse.x * 10, mouse.y * 5, 0);
    for (let i = 0; i < particlesCount; i++) {
        const i3 = i * 3;
        const particlePos = new THREE.Vector3(positions[i3], positions[i3 + 1], positions[i3 + 2]);
        const distance = particlePos.distanceTo(mouse3D);
        if (distance < repelRadius) {
            const repelVec = new THREE.Vector3().subVectors(particlePos, mouse3D).normalize();
            particlesData[i].velocity.add(repelVec.multiplyScalar(repelStrength));
        }
        const returnVec = new THREE.Vector3().subVectors(particlesData[i].originalPos, particlePos);
        particlesData[i].velocity.add(returnVec.multiplyScalar(returnStrength));
        particlesData[i].velocity.multiplyScalar(damping);
        positions[i3] += particlesData[i].velocity.x;
        positions[i3 + 1] += particlesData[i].velocity.y;
        positions[i3 + 2] += particlesData[i].velocity.z;
    }
    particlesGeometry.attributes.position.needsUpdate = true;

    const targetX = mouse.x * 1.5;
    const targetY = mouse.y * 1.5;
    logoGroup.rotation.y += 0.05 * (targetX - logoGroup.rotation.y);
    logoGroup.rotation.x += 0.05 * (targetY - logoGroup.rotation.x);
    logoGroup.position.y = Math.sin(elapsedTime * 0.5) * 0.2;
    composer.render();
    requestAnimationFrame(animate);
}
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    composer.setSize(window.innerWidth, window.innerHeight);
});
animate();