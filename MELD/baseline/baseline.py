import argparse
import tensorflow as tf
from sklearn.model_selection import train_test_split
from data_helpers import Dataloader
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_recall_fscore_support
from sklearn.metrics import accuracy_score
import os, pickle
import numpy as np
import wandb

wandb.login()

# os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
# os.environ["CUDA_VISIBLE_DEVICES"]="0"

class bc_LSTM:

	def __init__(self, args):
		self.classification_mode = args.classify
		self.modality = args.modality
		self.PATH = "./data/models/{}_weights_{}.model.keras".format(args.modality,self.classification_mode.lower())
		self.OUTPUT_PATH = "./data/pickles/{}_{}.pkl".format(args.modality,self.classification_mode.lower())
		print("Model initiated for {} classification".format(self.classification_mode))


	def load_data(self,):

		print('Loading data')
		self.data = Dataloader(mode = self.classification_mode)

		if self.modality == "text":
			self.data.load_text_data()
		elif self.modality == "audio":
			self.data.load_audio_data()
		elif self.modality == "bimodal":
			self.data.load_bimodal_data()
		elif self.modality == "audio_video_model":
			self.data.load_audio_video_model()
		elif self.modality == "video":
			self.data.load_video_data()
		else:
			exit()

		self.train_x = self.data.train_dialogue_features
		self.val_x = self.data.val_dialogue_features
		self.test_x = self.data.test_dialogue_features

		self.train_y = self.data.train_dialogue_label
		self.val_y = self.data.val_dialogue_label
		self.test_y = self.data.test_dialogue_label

		self.train_mask = self.data.train_mask
		self.val_mask = self.data.val_mask
		self.test_mask = self.data.test_mask

		self.train_id = self.data.train_dialogue_ids.keys()
		self.val_id = self.data.val_dialogue_ids.keys()
		self.test_id = self.data.test_dialogue_ids.keys()

		self.sequence_length = self.train_x.shape[1]
		
		self.classes = self.train_y.shape[2]
			


	def calc_test_result(self, pred_label, test_label, test_mask):
		f1_metric = tf.keras.metrics.F1Score()
		true_label=[]
		predicted_label=[]
		t_label, p_label = [], []

		for i in range(pred_label.shape[0]):
			for j in range(pred_label.shape[1]):
				if test_mask[i,j]==1:
					true_label.append(np.argmax(test_label[i,j] ))
					predicted_label.append(np.argmax(pred_label[i,j] ))
					t_label.append(test_label[i, j])
					p_label.append(pred_label[i, j])

		f1_metric.update_state(t_label, p_label)
		print("Confusion Matrix :")
		print(confusion_matrix(true_label, predicted_label))
		print("Classification Report :")
		print(classification_report(true_label, predicted_label, digits=4))
		print('Weighted FScore: \n ', precision_recall_fscore_support(true_label, predicted_label, average='weighted'))
		print('F1 Score: \n', f1_metric.result())


	def get_audio_model(self):

		# Modality specific hyperparameters
		self.epochs = 100
		self.batch_size = 50

		# Modality specific parameters
		self.embedding_dim = self.train_x.shape[2]

		self.configs = dict(
			num_classes = self.classes,
			batch_size = self.batch_size,
			epochs = self.epochs,
		)

		print("Creating Model...")
		
		inputs = tf.keras.layers.Input(shape=(self.sequence_length, self.embedding_dim), dtype='float32')
		masked = tf.keras.layers.Masking(mask_value =0)(inputs)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='tanh', return_sequences = True, dropout=0.4))(masked)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='tanh', return_sequences = True, dropout=0.4), name="utter")(lstm)
		output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.classes,activation='softmax'))(lstm)

		model = tf.keras.models.Model(inputs, output)
		return model
	
	def get_video_model(self):

		# Modality specific hyperparameters
		self.epochs = 1
		self.batch_size = 50

		# Modality specific parameters
		self.embedding_dim = self.train_x.shape[2]

		self.configs = dict(
			num_classes = self.classes,
			batch_size = self.batch_size,
			epochs = self.epochs,
		)

		print("Creating Model...")
		
		inputs = tf.keras.layers.Input(shape=(self.sequence_length, self.embedding_dim), dtype='float32')
		masked = tf.keras.layers.Masking(mask_value =0)(inputs)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='tanh', return_sequences = True, dropout=0.4))(masked)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='tanh', return_sequences = True, dropout=0.4), name="utter")(lstm)
		output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.classes,activation='softmax'))(lstm)

		model = tf.keras.models.Model(inputs, output)
		return model


	def get_text_model(self):

		# Modality specific hyperparameters
		self.epochs = 100
		self.batch_size = 50

		# Modality specific parameters
		self.embedding_dim = self.data.W.shape[1]

		# For text model
		self.vocabulary_size = self.data.W.shape[0]
		self.filter_sizes = [3,4,5]
		self.num_filters = 512

		self.configs = dict(
			num_classes = self.classes,
			batch_size = self.batch_size,
			epochs = self.epochs,
		)

		print("Creating Model...")

		sentence_length = self.train_x.shape[2]

		# Initializing sentence representation layers
		embedding = tf.keras.layers.Embedding(input_dim=self.vocabulary_size, output_dim=self.embedding_dim, embeddings_initializer=tf.keras.initializers.Constant(self.data.W), input_shape=(self.batch_size, sentence_length), trainable=False)
		conv_0 = tf.keras.layers.Conv2D(self.num_filters, kernel_size=(self.filter_sizes[0], self.embedding_dim), padding='valid', kernel_initializer='normal', activation='relu')
		conv_1 = tf.keras.layers.Conv2D(self.num_filters, kernel_size=(self.filter_sizes[1], self.embedding_dim), padding='valid', kernel_initializer='normal', activation='relu')
		conv_2 = tf.keras.layers.Conv2D(self.num_filters, kernel_size=(self.filter_sizes[2], self.embedding_dim), padding='valid', kernel_initializer='normal', activation='relu')
		maxpool_0 = tf.keras.layers.MaxPool2D(pool_size=(sentence_length - self.filter_sizes[0] + 1, 1), strides=(1,1), padding='valid')
		maxpool_1 = tf.keras.layers.MaxPool2D(pool_size=(sentence_length - self.filter_sizes[1] + 1, 1), strides=(1,1), padding='valid')
		maxpool_2 = tf.keras.layers.MaxPool2D(pool_size=(sentence_length - self.filter_sizes[2] + 1, 1), strides=(1,1), padding='valid')
		dense_func = tf.keras.layers.Dense(100, activation='tanh', name="dense")
		dense_final = tf.keras.layers.Dense(units=self.classes, activation='softmax')
		reshape_func = tf.keras.layers.Reshape((sentence_length, self.embedding_dim, 1))

		def slicer(x, index):
			return x[:,tf.constant(index, dtype='int32'),:]

		def slicer_output_shape(input_shape):
			shape = list(input_shape)
			assert len(shape) == 3  # batch, seq_len, sent_len
			new_shape = (shape[0], shape[2])
			return new_shape

		def reshaper(x):
			return tf.expand_dims(x, axis=3)

		def flattener(x):
			x = tf.reshape(x, [-1, x.shape[1]*x.shape[3]])
			return x

		def flattener_output_shape(input_shape):
			shape = list(input_shape)
			new_shape = (shape[0], 3*shape[3])
			return new_shape

		inputs = tf.keras.layers.Input(shape=(self.sequence_length, sentence_length), dtype='int32')
		cnn_output = []
		for ind in range(self.sequence_length):
			
			local_input = tf.keras.layers.Lambda(slicer, output_shape=slicer_output_shape, arguments={"index":ind})(inputs) # Batch, word_indices
			
			#cnn-sent
			emb_output = embedding(local_input)
			reshape = tf.keras.layers.Lambda(reshaper)(emb_output)
			concatenated_tensor = tf.keras.layers.Concatenate(axis=1)([maxpool_0(conv_0(reshape)), maxpool_1(conv_1(reshape)), maxpool_2(conv_2(reshape))])
			flatten = tf.keras.layers.Lambda(flattener, output_shape=flattener_output_shape,)(concatenated_tensor)
			dense_output = dense_func(flatten)
			dropout = tf.keras.layers.Dropout(0.5)(dense_output)
			cnn_output.append(dropout)

		def stack(x):
			return tf.stack(x, axis=1)
		cnn_outputs = tf.keras.layers.Lambda(stack)(cnn_output)

		masked = tf.keras.layers.Masking(mask_value =0)(cnn_outputs)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='relu', return_sequences = True, dropout=0.3))(masked)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='relu', return_sequences = True, dropout=0.3), name="utter")(lstm)
		output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.classes,activation='softmax'))(lstm)

		model = tf.keras.models.Model(inputs, output)
		return model

	def get_bimodal_model(self):

		# Modality specific hyperparameters
		self.epochs = 100
		self.batch_size = 10

		# Modality specific parameters
		self.embedding_dim = self.train_x.shape[2]

		self.configs = dict(
			num_classes = self.classes,
			batch_size = self.batch_size,
			epochs = self.epochs,
		)

		print("Creating Model...")
		
		inputs = tf.keras.layers.Input(shape=(self.sequence_length, self.embedding_dim), dtype='float32')
		masked = tf.keras.layers.Masking(mask_value =0)(inputs)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(300, activation='tanh', return_sequences = True, dropout=0.4), name="utter")(masked)
		output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.classes,activation='softmax'))(lstm)

		model = tf.keras.models.Model(inputs, output)
		return model
	
	def get_trimodal_model(self):

		# Modality specific hyperparameters
		self.epochs = 100
		self.batch_size = 10

		# Modality specific parameters
		self.embedding_dim = self.train_x.shape[2]

		self.configs = dict(
			num_classes = self.classes,
			batch_size = self.batch_size,
			epochs = self.epochs,
		)

		print("Creating Model...")
		
		inputs = tf.keras.layers.Input(shape=(self.sequence_length, self.embedding_dim), dtype='float32')
		masked = tf.keras.layers.Masking(mask_value =0)(inputs)
		lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(500, activation='tanh', return_sequences = True, dropout=0.4), name="utter")(masked)
		output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.classes,activation='softmax'))(lstm)

		model = tf.keras.models.Model(inputs, output)
		return model




	def train_model(self):

		checkpoint = tf.keras.callbacks.ModelCheckpoint(self.PATH, monitor='val_loss', verbose=1, save_best_only=True, mode='auto')

		if self.modality == "audio":
			model = self.get_audio_model()

		elif self.modality == "text":
			model = self.get_text_model()

		elif self.modality == "video":
			model = self.get_video_model()

		elif self.modality == "bimodal":
			model = self.get_bimodal_model()

		elif self.modality == "trimodal":
			model = self.get_trimodal_model()
			

		model.compile(
				optimizer='adam', 
				loss='categorical_crossentropy',
				weighted_metrics=[tf.keras.metrics.CategoricalAccuracy(), 
			 			# tf.keras.metrics.F1Score(), 
	   					# tfa.metrics.F1Score(num_classes=self.classes),
			 			tf.keras.metrics.Recall(), 
						tf.keras.metrics.Precision()]
		)
		run = wandb.init(
			project = f"MELD_{self.modality}_{self.classification_mode}",
			config = self.configs
		)

		early_stopping = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10)
		model.fit(self.train_x, self.train_y,
		                epochs=self.epochs,
		                batch_size=self.batch_size,
		                sample_weight=self.train_mask,
		                shuffle=True, 
		                callbacks=[wandb.keras.WandbMetricsLogger(log_freq=10), early_stopping, checkpoint],
		                validation_data=(self.val_x, self.val_y, self.val_mask))
		
		self.calc_test_result(model.predict(self.test_x), self.test_y, self.test_mask, run)
		run.finish()
		self.test_model()



	def test_model(self):

		model = tf.keras.models.load_model(self.PATH)
		intermediate_layer_model = tf.keras.models.Model(inputs=model.input, outputs=model.get_layer("utter").output)

		intermediate_output_train = intermediate_layer_model.predict(self.train_x)
		intermediate_output_val = intermediate_layer_model.predict(self.val_x)
		intermediate_output_test = intermediate_layer_model.predict(self.test_x)

		train_emb, val_emb, test_emb = {}, {}, {}
		for idx, ID in enumerate(self.train_id):
			train_emb[ID] = intermediate_output_train[idx]
		for idx, ID in enumerate(self.val_id):
			val_emb[ID] = intermediate_output_val[idx]
		for idx, ID in enumerate(self.test_id):
			test_emb[ID] = intermediate_output_test[idx]
		pickle.dump([train_emb, val_emb, test_emb], open(self.OUTPUT_PATH, "wb"))

		self.calc_test_result(model.predict(self.test_x), self.test_y, self.test_mask)
		



if __name__ == "__main__":

	# Setup argument parser
	parser = argparse.ArgumentParser()
	parser.required=True
	parser.add_argument("-classify", help="Set the classifiction to be 'Emotion' or 'Sentiment'", required=True)
	parser.add_argument("-modality", help="Set the modality to be 'text' or 'audio' or 'bimodal' or 'video' or 'trimodal'", required=True)
	parser.add_argument("-train", default=False, action="store_true" , help="Flag to intiate training")
	parser.add_argument("-test", default=False, action="store_true" , help="Flag to initiate testing")
	args = parser.parse_args()

	if args.classify.lower() not in ["emotion", "sentiment"]:
		print("Classification mode hasn't been set properly. Please set the classifiction flag to be: -classify Emotion/Sentiment")
		exit()
	if args.modality.lower() not in ["text", "audio", "bimodal", "video", "trimodal"]:
		print("Modality hasn't been set properly. Please set the modality flag to be: -modality text/audio/bimodal")
		exit()

	args.classify = args.classify.title()
	args.modality = args.modality.lower()
	
	# Check directory existence
	for directory in ["./data/pickles", "./data/models"]:
		if not os.path.exists(directory):
			os.makedirs(directory)


	model = bc_LSTM(args)
	model.load_data()

	if args.test:
		model.test_model()
	else:
		model.train_model()