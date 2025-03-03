import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import numpy as np
import time
import threading
import librosa
import math
from src.Capabilities.debug_mode import set_debug_mode, get_debug_mode

class Display:
	def __init__(self):
		"""Initialize the OpenGL-based overlay window."""
		pygame.init()
		self.width, self.height = 800, 800
		self.screen = pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
		pygame.display.set_caption("VORTEX Audio Visualization (OpenGL)")

		self.running = True
		self.last_update_time = time.time()

		# ✅ Initialize OpenGL
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		# ✅ Create and bind shader
		self.shader = self.create_shader()
		glUseProgram(self.shader)

		# ✅ Initialize particle data
		self.num_particles = 500
		self.particle_positions = np.random.rand(self.num_particles, 2) * 2 - 1
		self.particle_velocities = np.random.rand(self.num_particles, 2) * 0.02 - 0.01
		self.particle_sizes = np.ones(self.num_particles) * 0.02

		# ✅ Start the OpenGL loop in a separate thread
		self.thread = threading.Thread(target=self.run, daemon=True)
		self.thread.start()

	def create_shader(self):
		"""Compiles and returns an OpenGL shader program."""
		vertex_shader = """
		#version 330 core
		layout (location = 0) in vec2 aPos;
		uniform float sizeFactor;
		void main() {
			gl_Position = vec4(aPos, 0.0, 1.0);
			gl_PointSize = sizeFactor * 20.0;
		}
		"""

		fragment_shader = """
		#version 330 core
		out vec4 FragColor;
		void main() {
			float alpha = 1.0 - length(gl_PointCoord - vec2(0.5, 0.5)) * 2.0;
			FragColor = vec4(1.0, 1.0, 0.5, alpha);
		}
		"""

		shader = glCreateProgram()
		
		# ✅ Compile and attach shaders
		vert_shader = glCreateShader(GL_VERTEX_SHADER)
		glShaderSource(vert_shader, vertex_shader)
		glCompileShader(vert_shader)
		if glGetShaderiv(vert_shader, GL_COMPILE_STATUS) != GL_TRUE:
			print("Vertex Shader Error:", glGetShaderInfoLog(vert_shader))

		frag_shader = glCreateShader(GL_FRAGMENT_SHADER)
		glShaderSource(frag_shader, fragment_shader)
		glCompileShader(frag_shader)
		if glGetShaderiv(frag_shader, GL_COMPILE_STATUS) != GL_TRUE:
			print("Fragment Shader Error:", glGetShaderInfoLog(frag_shader))

		glAttachShader(shader, vert_shader)
		glAttachShader(shader, frag_shader)

		glLinkProgram(shader)
		if glGetProgramiv(shader, GL_LINK_STATUS) != GL_TRUE:
			print("Shader Program Linking Error:", glGetProgramInfoLog(shader))

		return shader

	def react_to_audio(self, audio_file):
		"""Reads an MP3 file, analyzes it in real-time, and updates visuals."""
		y, sr = librosa.load(audio_file, sr=None)
		waveform = np.abs(y) / np.max(np.abs(y))
		fft_spectrum = np.abs(librosa.stft(y, n_fft=2048)).mean(axis=1)

		self.update_visualizer(waveform, fft_spectrum)

	def update_visualizer(self, waveform, fft_spectrum):
		"""Receives analyzed audio data and updates visuals."""
		avg_amplitude = np.mean(waveform) if len(waveform) > 0 else 0
		max_freq = np.max(fft_spectrum) if len(fft_spectrum) > 0 else 0

		# ✅ Make particles react to the audio
		self.particle_sizes = 0.02 + avg_amplitude * 0.1
		self.particle_velocities[:, 1] += (np.random.rand(self.num_particles) - 0.5) * avg_amplitude * 0.02

		self.last_update_time = time.time()

	def run(self):
		"""Runs the OpenGL loop and updates the overlay in real-time."""
		clock = pygame.time.Clock()

		while self.running:
			for event in pygame.event.get():
				if event.type == QUIT:
					self.running = False
					pygame.quit()
					return  # ✅ Exit cleanly

			glClear(GL_COLOR_BUFFER_BIT)

			# ✅ Update particle positions
			self.particle_positions += self.particle_velocities

			# ✅ Keep particles within screen bounds
			self.particle_positions = np.clip(self.particle_positions, -1, 1)

			# ✅ Bind shader and update uniform
			glUseProgram(self.shader)
			sizeFactor = min(2.0, max(0.2, np.mean(self.particle_sizes)))
			glUniform1f(glGetUniformLocation(self.shader, "sizeFactor"), sizeFactor)

			# ✅ Enable vertex array and bind data
			glEnableClientState(GL_VERTEX_ARRAY)
			glVertexPointer(2, GL_FLOAT, 0, self.particle_positions.astype(np.float32))

			# ✅ Draw points
			glDrawArrays(GL_POINTS, 0, self.num_particles)

			# ✅ Disable after drawing
			glDisableClientState(GL_VERTEX_ARRAY)

			pygame.display.flip()
			clock.tick(60)  # Run at 60 FPS

			# ✅ Auto-hide after 90 seconds of inactivity
			if time.time() - self.last_update_time > 90:
				self.running = False
				pygame.quit()
				return  # ✅ Ensure clean exit

	def stop(self):
		"""Stops the overlay and closes the OpenGL window safely."""
		self.running = False
		pygame.quit()

#display = Display()
